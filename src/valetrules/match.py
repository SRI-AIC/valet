from functools import total_ordering
import json
from typing import Tuple, Text, Dict, Union, List

from nlpcore.dbfutil import SimpleClass, GenericException

"""
Provides a taxonomy of match classes roughly mirroring the different kinds 
of pattern expression. Classes include FAMatch, FAArcMatch, CoordMatch, 
and Frame.

Match instances track matches of patterns against token sequences, 
also tracking "submatches", matches of other patterns referenced by name 
by the given pattern.
"""

# TODO The FAArcMatch subclass changes the meaning of the end index field  
# from the [)-style end of all the other subclasses to []-style.
# Also, FAArcMatches are sometimes created with begin and end reversed.
# The get_begin_end, get_exclusive_end, and begin/end_offset methods 
# help to work around some of those differences, but there have been bugs 
# and very likely still are.
# Short of changing the FAArcMatch convention end index convention and ensuring
# begin < end (tricky because these are sometimes changed after ctor sets them),
# I'm thinking probably these methods should be used almost universally
# instead of directly acessing the end attribute, including in most of 
# these methods.
# E.g., do we ever have to compare matches of different classes? 
# You'd think so, and if so there are probably bugs related to that.

# TODO Note that FAMatch objects are also created for token test matches, 
# not just phrase expression matches. 
# Since we have separate classes for FAArcMatch and CoordMatch, and those 
# inherit from FAMatch, most likely it would make sense to have a new base 
# class Match, and a new match type TTMatch, and have all the leaf match 
# types inherit from Match instead of FAMatch, with the possible exception 
# of FAArcMatch, which may want to inherit some of FAMatch's methods.
@total_ordering
class FAMatch(SimpleClass):
    """
    Tracks extractions returned by extractors.
    An FAMatch object has the following core member variables:
    seq: a reference to the TokenSequence object in which the match is found
    begin: the index of the first token in the matching phrase
    end: the index of the first token after the matching phrase, or the length of the token sequence if the match is coterminous with the end of the token sequence
    submatches: a list of matches extracted by extractors referenced by name
    name: if a match was returned by an extractor referenced by name, this field holds the name of the extractor
    """

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        if not hasattr(self, "submatches"):
            self.submatches = []
        # Some subclasses set these from other values other than **args, 
        # so they're not necessarily defined here.
        if hasattr(self, "begin") and hasattr(self, "end") and self.end < self.begin:
            pass
            # print("FAMatch(%s).__init__(begin=%d end=%d)" % (type(self).__name__, self.begin, self.end))
            # self.begin, self.end = self.end, self.begin

    def get_begin_end(self):
        """Return [)-style token indices, also reversing the internal begin/end fields if needed."""
        # Account for FAArcMatch indices being potentially reversed.
        if self.end < self.begin:
            begin, end = self.end, self.begin
        else:
            begin, end = self.begin, self.end
        # Account for FAArcMatch end indices being different.
        end_adj = self.get_exclusive_end() - self.end
        end += end_adj
        return begin, end

    def get_exclusive_end(self):
        """Return token index one past the last token of the match
        assuming self.end (not self.begin) is really the end."""
        return self.end

    # This was used in only one place (FiniteAutomaton.scan) 
    # and seems like a bad idea anyway.
    # I do notice that the largely unused "bounds" arguments to
    # various scan/search/match/etc methods do use this convention,
    # and maybe the idea was that we might sometimes pass tuples or
    # arrays as bounds and other times pass match values, and wanted
    # to be able to use uniform syntax.
    # Still, when we do know it's a match argument it's clearer to use
    # m.begin/end instead of m[0/1].
    # def __getitem__(self, key):
    #     # TODO Should this call get_begin_end?
    #     if key == 0:
    #         return self.begin
    #     elif key == 1:
    #         return self.end

    def __lt__(self, other):
        # Current tests (12/2021) do not trigger any of these type checks
        # throughout this file, FWIW.
        # if type(other) is not type(self):
        #     raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        # This does get triggered, FWIW.
        # raise GenericException(msg=f"FAMatch.__lt__ called")
        if self.begin == other.begin:
            return self.end < other.end
        else:
            return self.begin < other.begin

    def __eq__(self, other):
        if other is None:
            return False
        # if type(other) is not type(self):
        #     raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        return self.begin == other.begin and self.end == other.end

    def __hash__(self):
        return hash((self.begin, self.end))

    def overlaps(self, other):
        # if type(other) is not type(self):
        #     raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        return (self.begin <= other.begin and other.begin < self.end or
                self.begin < other.end and other.end <= self.end or
                other.begin <= self.begin and self.begin < other.end or
                other.begin < self.end and self.end <= other.end)

    def covers(self, index):
        return self.begin <= index and index < self.end

    def start_offset(self, absolute=False):
        """
        The character offset into the input text at which the match starts.
        If absolute=True, the offset is relative to the start of the complete 
        text, otherwise relative to the start of the sentence.
        """
        tseq = self.seq
        begin, end = self.get_begin_end()
        offs = tseq.get_normalized_offset(begin)
        if absolute:
            offs += tseq.offset
        return offs

    def end_offset(self, absolute=False):
        """
        The (exclusive) character offset into the input text at which the match ends.
        If absolute=True, the offset is relative to the start of the complete 
        text, otherwise relative to the start of the sentence.
        """
        tseq = self.seq
        begin, end = self.get_begin_end()
        if end == 0:  # could be a match FAMatch([START],0,0,)
            offs = 0
        else:
            offs = tseq.get_normalized_offset(end - 1) + tseq.lengths[end - 1]
        if absolute:
            offs += tseq.offset
        return offs

    def add_submatch(self, m):
        try:
            self.submatches.append(m)
        except:
            self.submatches = [m]

    # (Probably no strong reason for this to be a generator, probably just 
    # that we don't want to expose our own list, and prefer a generator 
    # to copying the list.)
    def get_submatches(self):
        """
        Generates the submatches from the internally held list field.
        """
        for m in self.submatches:
            yield m

    # This method is used by the select coordinator, and determines 
    # what can be selected. 
    # It is also used by the operator_map method, which has to do with 
    # constructing Frames, which presumably want similar semantics.
    def all_submatches(self, name=None):
        """
        Returns all matches associated with any named subexpressions 
        in the top-level extractor or any of its descendants.
        If name is specified, restricts to that name.
        """
        result = []
        for m in self.get_submatches():
            # Where does an unnamed submatch come from?
            # AFAICT it comes from an unnamed nested coordinator expression, 
            # such as the match expression in 
            # specific_fire_behavior ~ select(any, match(complete_fire_behavior, _)) 
            # or implicitly in the equivalent 
            # specific_fire_behavior ~ select(any, complete_fire_behavior).
            if name is None or hasattr(m, 'name') and m.name == name:
                result.append(m)
            for sm in m.all_submatches(name):  # recurse into submatches
                result.append(sm)
        return result

    def print_match_trace(self, indent=0):
        print("%s%s" % ((' ' * indent), self))
        for m in self.get_submatches():
            m.print_match_trace(indent=indent+2)

    # Similar to an xpath like /**/name1/**/name2/**/.../**/nameN.
    def query(self, *names) -> 'FAMatch':
        """Used with frames, for finding in the match/submatch tree a sequence
        of matches of the given extractor names, corresponding to the sequence
        of extractor names on the RHS of a frame slot definition.
        It is allowed to have matches of additional extractors in the path
        through the tree, in between the given extractor names.
        Yields the matches corresponding to the last extractor name."""
        if len(names) == 0:
            return
        if hasattr(self, 'name') and names[0] == self.name:
            names = names[1:]
            if len(names) == 0:
                yield self
                return
        for m in self.get_submatches():
            for sm in m.query(*names):  # recurse into submatches
                yield sm

    def matching_text(self):
        """
        The verbatim matching string ["as a phrase"?].
        """
        tseq = self.seq
        if self.begin == self.end:
            return ''
        return tseq.get_normalized_text()[self.start_offset():self.end_offset()]

    def matching_lemma(self):
        lemmastrings = []
        for toki in range(self.begin,self.end):
            if not hasattr(self.seq, 'get_token_annotation'):
                lemma = self.seq[toki].text.lower()
            else:
                lemma = self.seq.get_token_annotation("lemma", toki).lower()
            lemmastrings += [lemma]
        return " ".join(lemmastrings)

    def widen(self, maximize=False):
        return self

    def __str__(self):
        # Can comment lines in and out here to change what is printed if needed for debug.
        field_to_abbr = { 
            "submatches": "ss"
        }
        list_fields = [
            "submatches"
        ]
        return self._str_aux(field_to_abbr, list_fields)

    def _str_aux(self, field_to_abbr, list_fields):

        to_join = []
        for field in field_to_abbr.keys():
            if hasattr(self, field):
                if field not in list_fields:
                    to_join.append(field_to_abbr[field] + "=" + str(getattr(self, field)))
                elif len(getattr(self, field)) > 0:
                    to_join.append(field_to_abbr[field] + "=" + "[" + ", ".join(str(e) for e in getattr(self, field)) + "]")
        fields = "" if len(to_join) == 0 else ", " + ",".join(to_join)

        typ = type(self).__name__
        if hasattr(self, 'name'):
            return "%s([%s],%d,%d,%s%s)" % (typ, self.name, self.begin, self.end, self.matching_text(), fields)
        else:
            return "%s(%d,%d,%s%s)" % (typ, self.begin, self.end, self.matching_text(), fields)

    def operator_map(self):
        return {}

    def frames(self):

        if hasattr(self, 'frame_extractor'):
            yield self.frame_extractor.extract_from_match(self)
            return

        omap = self.operator_map()

        def _gen_frame(keys):
            if len(keys) == 0:
                yield Frame()
            else:
                for f in _gen_frame(keys[1:]):
                    key = keys[0]
                    val = omap[key]
                    if isinstance(val, list):
                        for v in val:
                            f2 = Frame(**f.fields)
                            f.set_field(key, v)
                            yield f
                    else:
                        f.set_field(key, val)
                        yield f

        for frame in _gen_frame(list(omap.keys())):
            yield frame
        

# Note that this subclass changes the meaning of the end variable as defined 
# in its superclass FAMatch, such that in FAArcMatch it's the index OF 
# the end token rather than the index of the token AFTER the end token.
class FAArcMatch(FAMatch):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.end < self.begin:
            pass
            # print("FAArcMatch.__init__(begin=%d end=%d)" % (self.begin, self.end))
            # Unfortunately, reversing begin and end here runs afoul 
            # of checks such as "if m is not None and m.end != start" 
            # in FiniteAutomaton.matches.
            # print("FAArcMatch.__init__(begin=%d end=%d); reversing begin and end" % (self.begin, self.end))
            # self.begin, self.end = self.end, self.begin

    def get_exclusive_end(self):
        """Return token index one past the last token of the match
        assuming self.end (not self.begin) is really the end."""
        return self.end + 1

    # TODO Do we ever have to compare matches of different classes?
    # Would the difference between this method and the FAMatch method 
    # be a problem?
    def overlaps(self, other):
        # if type(other) is not type(self):
        #     raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        return (self.begin <= other.begin and other.begin <= self.end or
                self.begin <= other.end and other.end <= self.end or
                other.begin <= self.begin and self.begin <= other.end or
                other.begin <= self.end and self.end <= other.end)

    # Ditto.
    def covers(self, index):
        return self.begin <= index and index <= self.end


class FARootMatch(FAMatch):

    """
    A special match object that only matches the root of the parse tree.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.begin = -1
        self.end = len(self.seq)

    def overlaps(self, other):
        return False

    def __str__(self):
        return "FARootMatch"


# The fields of CoordMatch are currently somewhat haphazard, or at least 
# not well documented, in terms of their intended function and meaning. 
#
# Our current nominal rule for the behavior of the select coordinator 
# is that "*any* named extractor implicated in the production of a match 
# stream is available to 'select'", although currently inverted filter and 
# diff operators don't strictly conform to that. 
# Also, there are certain somewhat unintuitive cases as illustrated in 
# the test_select_2 test from test_coordinator.py; see discussion there.
#
# Selection is implemented via the all_submatches method, so what that 
# returns determines what is selectable. 
# Currently, all the fields that are set are returned by get_submatches, 
# which is called recursively by all_submatches, including left, right, 
# submatch, supermatch, etc. 
#
# The main functional purpose of setting those fields is to implement 
# the select semantics. A second functional purpose appears to be in 
# the extraction of matches for frames (which also calls all_submatches), 
# which probably follows the same select semantics.
#
# Beyond that, there seems to be no functional reason for separately 
# identifying left, right, submatch, supermatch, etc (which can sometimes 
# have the same values). Functionally, they are all a kind of generic submatch.
#
# Presumably part of the idea is that by having separately named fields 
# instead of just a list of submatches, downstream code that wants to 
# further dissect and analyze the matches has some additional information 
# available about where that particular submatch came from.
# However, I am not aware of any code that currently does so.
#
# The "left" and "right" fields designate the matches from the first and 
# second <coord_expr> (aka "feed") arguments to the join family and connects 
# coordinators.
# The "left" field is also used to designate the matches from the single 
# <coord_expr> ("feed") argument to those coordinators that have just one.
# I will let Dayne fill in his intended meaning of "submatch" and "supermatch". 
#
class CoordMatch(FAMatch):

    # It's OK if some of left, right, supermatch, submatch, etc are the same match.
    def __init__(self, m, **args):
        """
        The m argument determines the extent of the match.
        """
        # We used to use "m" as the default "left" if no left was passed, 
        # but not anymore.
        # We also used to promote the "m" arg's "submatches" values to 
        # ourselves, but now we just let the recursion in all_submatches 
        # get them, which it will do as long as the "m" value is also 
        # one of left, right, submatch, supermatch, etc, which is why 
        # I added submatch=pm to the calls from the match and select 
        # coordinators, where that wasn't the case before.
        super().__init__(**args)
        begin, end = m.get_begin_end()
        self.seq, self.begin, self.end = m.seq, begin, end

    # Compare to get_submatches of FAMatch, which generates values from 
    # the submatches field. We probably don't need to be a generator.
    # The main thing is not to be recursive; all_submatches 
    # (which we inherit from FAMatch) is the method that is recursive.
    def get_submatches(self):
        """Non-recursive. Result includes values from attributes 
        left, right, submatch, submatches. Also includes members."""
        submatches = {}
        if hasattr(self, 'left') and self.left is not None:
            submatches[id(self.left)] = self.left
        if hasattr(self, 'right') and self.right is not None:
            submatches[id(self.right)] = self.right
        if hasattr(self, 'submatch') and self.submatch is not None:
            submatches[id(self.submatch)] = self.submatch
        if hasattr(self, 'supermatch') and self.supermatch is not None:
            submatches[id(self.supermatch)] = self.supermatch

        # The experimental 'count' coordinator that I have started to 
        # implement will use the submatches field instead of the submatch 
        # field because it can have an arbitrary number of submatches, 
        # so we would want to return them for that.
        if hasattr(self, 'submatches') and self.submatches is not None:
            for submatch in self.submatches:
                submatches[id(submatch)] = submatch

        # "members" can be set by MergeCoordinator, which is experimental.
        if hasattr(self, 'members') and self.members is not None:
            for member in self.members:
                submatches[id(member)] = member
        return submatches.values()

    def operator_map(self):
        opmap = dict()
        #opmap[self.match.op.label] = self.solo_text()
        label = self.op.label
        if label is None:
            if hasattr(self, "left"):
                try:
                    label = self.left.op.label
                except:
                    pass
            if label is None and hasattr(self, "supermatch"):
                try:
                    label = self.supermatch.op.label
                except:
                    pass
        if label is None:
            pass
        elif ":" in label:
            label, colon, subcomponent = label.partition(":")
            opmap[label] = [x.matching_lemma() for x in self.all_submatches(subcomponent)]
            if len(opmap[label]) == 1:
                opmap[label] = opmap[label][0]
        else:
            opmap[label] = self.matching_lemma()
        if hasattr(self, "submatch"):
            if isinstance(self.submatch, CoordMatch):
                opmap.update(self.submatch.operator_map())
        if hasattr(self, "supermatch"):
            if isinstance(self.supermatch,CoordMatch):
                opmap.update(self.supermatch.operator_map())
        return opmap

    def solo_text(self):
        return super().matching_text()

#    def matching_text(self):
#        if hasattr(self, "submatch") and self.submatch:
#            full_string = self.seq.text[min(self.start_offset(),self.submatch.start_offset()):max(self.end_offset(),self.submatch.end_offset())]
#            return "(%s:%s) %s" % (self.solo_text(),self.submatch.matching_text(),full_string)
#        else:
#            return super().matching_text()

    def widen(self, maximize=False):
        """
        For coordination matches that select matches from one of their 
        input streams, this produces matches that covers the extent 
        of both matches and intervening text.
        If maximize=True, also widens to cover the extent of any
        submatches or supermatches (and recursively also cover
        the extent of their other matches, submatches, or supermatches).
        """
        widened = CoordMatch(self, **vars(self))
        if hasattr(widened, 'left') and hasattr(widened, 'right'):
            widened.begin = min(widened.left.begin, widened.right.begin)
            widened.end = max(widened.left.end, widened.right.end)
        if maximize:
            # Note: widen below returns widened *copies* of the submatch and 
            # supermatch, which we throw away after extracting their extents.
            if hasattr(widened, 'submatch'):
                sm = self.submatch.widen(True)
                widened.begin = min(widened.begin, sm.begin)
                widened.end = max(widened.end, sm.end)
            if hasattr(widened, 'supermatch'):
                sm = self.supermatch.widen(True)
                widened.begin = min(widened.begin, sm.begin)
                widened.end = max(widened.end, sm.end)
        return widened

    # This method knows more than it perhaps should about the
    # different coordinators that create the CoordMatch objects. 
    # Possibly should have some CoordMatch subclasses, possibly 
    # in a taxonomy based on the base classes FeedCoordinator, 
    # JoinCoordinator, etc.
    def __str__(self):
        # Can comment lines in and out here to change what is printed if needed for debug.
        field_to_abbr = { 
            "submatch": "sb",
            "submatches": "ss"
            #"supermatch": "sp",
            #"left": "l", 
            #"right": "r"
        }
        list_fields = [
            "submatches"
        ]
        return self._str_aux(field_to_abbr, list_fields)


class Frame(object):  # note not FAMatch subclass
    """Basically a dictionary whose keys are tuples of strings from the 
    RHS of VR rule language frame slot definitions, and whose values are 
    either single match instances (if there is only one value) or lists 
    of match instances (if there are multiple values). The lists are treated 
    as sets, and match instance equality is used to compare matches."""

    def __init__(self, **kwargs):
        self.fields: Dict[Tuple[Text], Union[FAMatch, List[FAMatch]]] = kwargs
    
    def set_field(self, field: Tuple[Text], val: Union[FAMatch, List[FAMatch]]):
        self.fields[field] = val

    def add_field(self, field: Tuple[Text], val: FAMatch):
        """Add if not present. Convert value from single match to 
        list when a second match is added for a field."""
        if field in self.fields:
            try:
                if val not in self.fields[field]:
                    self.fields[field].append(val)
            except TypeError:
                if val != self.fields[field]:
                    self.fields[field] = [ self.fields[field], val ]
        else:
            self.fields[field] = val

    def merge(self, other: 'Frame'):
        """Add fields and values from other that are not present in self."""
        for field, value in other.fields.items():
            if isinstance(value, list):
                values = value
            else:
                values = [value]
            for v in values:
                self.add_field(field, v)

    def subsumes(self, other: 'Frame'):
        """
        One frame subsumes another if it contains all of the same fields
        with the same values.
        """
        for k, v in other.fields.items():
            if (not k in self.fields) or v != self.fields[k]:
                return False
        return True

    def as_json_serializable(self):
        """Represent as dict suitable for conversion to JSON string.
        Match instances are represented by their matching_text()."""
        result = {}
        for fname, values in self.fields.items():
            if isinstance(values, list):
                value_set = set(values)
                value_strings = [m.matching_text() for m in value_set]
                result[fname] = value_strings
            else:
                result[fname] = values.matching_text()
        return result

    def as_json_serializable_with_offsets(self, source, sentence_offset, pattern):
        result = {"source": source, "pattern": pattern}
        for fname, values in self.fields.items():
            if isinstance(values, list):
                value_set = set(values)
                value_strings = [{'text': m.matching_text(), 'start': m.start_offset() + sentence_offset, 'end': m.end_offset() + sentence_offset} for m in value_set]
                result[fname] = value_strings
            else:
                result[fname] = {'text': values.matching_text(), 'start': values.start_offset() + sentence_offset, 'end': values.end_offset() + sentence_offset}
        return result

    def as_json(self):
        """Represent as JSON string."""
        return json.dumps(self.as_json_serializable())

    def as_json_with_offsets(self, source, sentence_offset, pattern):
        return json.dumps(self.as_json_serializable_with_offsets(source, sentence_offset, pattern))
