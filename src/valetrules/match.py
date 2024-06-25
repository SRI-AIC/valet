from abc import ABC, abstractmethod
from functools import total_ordering
import json
from copy import copy
from typing import Dict, Iterator, List, Optional, Text, Tuple, Union, TYPE_CHECKING

from ordered_set import OrderedSet

from nlpcore.dbfutil import GenericException
if TYPE_CHECKING:
    from .coordinator import Coordinator

"""
Provides a taxonomy of match classes roughly mirroring the different kinds
of pattern expression. Classes include FAMatch, FAArcMatch, CoordMatch,
and Frame.

Match instances track matches of patterns against token sequences,
also tracking "submatches", matches of other patterns referenced by name
by the given pattern.
"""


class TokenSequenceMismatchException(Exception):
    """Indicates non-meaningful comparison operation on matches
    from different token sequences."""
    def __init__(self, this: 'Match', other: 'Match',
                 message="Can't compare extents of matches from different token sequences (except for equality, which is never True)"):
        super().__init__(message)
        self.this = this
        self.other = other


# Type returned by get_extent().
Extent = Tuple[int, int]


# NOTE: The FAArcMatch subclass changes the meaning of the end index field
# from the [)-style end of (nearly) all the other subclasses to []-style.
# Also, FAArcMatches are sometimes created with begin and end reversed.
#
# The get_extent() method is the primary means of working around those
# differences.
# We've had lots of bugs in the area in the past, but hopefully all fixed.
# This method should often be used instead of directly acessing the begin/end
# attributes.

# FAMatch was the original base class, but we moved most of the functionality
# into this new base class Match.
@total_ordering
class Match(ABC):
    """
    Tracks extractions returned by extractors.
    A Match object has the following core member variables:
      seq: a reference to the TokenSequence object in which the match is found
      begin: the index of the first token in the matching phrase
      end: the index of the first token after the matching phrase, or the length of the token sequence if the match is coterminous with the end of the token sequence
      name: if a match was returned by an extractor referenced by name, this field holds the name of the extractor
    Note: The FAArcMatch subclass has different conventions for the begin
    and end indices. But for all subclasses, the get_extent() method returns
    begin/end values conforming to the above convention.
    """

    def __init__(self, seq, begin, end, name=None, **kwargs):
        self.seq = seq
        self.begin = begin
        self.end = end
        # Names are not necessarily passed in to the ctor,
        # and even if they are, they are generally overwritten
        # (conceivably with the same value) by the VRManager.
        self.name = name
        # Formerly implemented via SimpleClass.
        # Could go back to that if needed, eg for "defaults" arg.
        for arg, val in kwargs.items():
            self.__dict__[arg] = val

    def get_extent(self) -> Extent:
        """Return [)-style token indices, also reversing the internal begin/end fields if needed."""
        # This would have caught a bug at one point. Leaving commented for debugging if needed.
        # if self.begin > self.end:
        #     raise GenericException(msg=f"Bad state: Match extent has begin ({self.begin}) > end ({self.end})")
        return self.begin, self.end

    def get_frame(self):
        return None

    def set_frame(self, frame):
        raise TypeError("Attempt to set the frame of a simple match object")

    # We could potentially generalize this to allow comparisons on matches
    # from different tseqs derived from the same text (determined by checking
    # tseq[0].text is the same for each tseq), and comparing the tseq.offset
    # values, but perhaps not a good idea.
    def __lt__(self, other):
        """
        Self is less than other if self begins at an earlier token than other,
        or if they begin at the same token and self ends earlier than other.
        Raises exception if matches are from different token sequences.
        """
        if not isinstance(other, Match):
            raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        # Current tests (12/2021) do not trigger any of these type checks
        # throughout this file, FWIW.
        # Such comparisons were more of a concern before Dayne's fixes
        # to use methods like get_extent (now) and get_begin_end (before)
        # more widely.
        # if type(other) is not type(self):
        #     raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        # This does get triggered, FWIW.
        # raise GenericException(msg=f"Match.__lt__ called")
        if other.seq is not self.seq:
            raise TokenSequenceMismatchException(self, other)
        b, e = self.get_extent()
        ob, oe = other.get_extent()
        if b == ob:
            return e < oe
        else:
            return b < ob

    def __eq__(self, other):
        """
        Two matches are equal if they are from the same token sequence (by id)
        and cover the same textual extent.
        Unlike __lt__ and overlaps, does not throw exception if the matches
        are from different token sequences; this allows matches from
        different token sequences to be kept and looked up in collections.
        """
        if other is None:
            return False
        if not isinstance(other, Match):
            raise GenericException(msg=f"Comparing {type(self)} to {type(other)}")
        if other.seq is not self.seq:
            # Raising would preclude putting matches with different tseqs
            # into a single collection (lookup could raise exceptions).
            # raise TokenSequenceMismatchException(self, other)
            return False
        b, e = self.get_extent()
        ob, oe = other.get_extent()
        return b == ob and e == oe

    def __hash__(self):
        b, e = self.get_extent()
        # This can be more efficient, but would preclude, e.g.,
        # using a pickled dict with keys that are matches.
        # Dayne said if we had a use case such as that,
        # "we’d probably want to create a specialized API to service it".
        return hash((id(self.seq), b, e))
        # return hash((b, e))

    def overlaps(self, other):
        """
        Matches overlap if they have at least one token (by position) in common.
        Raises exception if matches are from different token sequences (by id).
        """
        if other.seq is not self.seq:
            raise TokenSequenceMismatchException(self, other)
        b, e = self.get_extent()
        ob, oe = other.get_extent()
        return b <= ob < e or b < oe <= e or ob <= b < oe or ob < e <= oe

    def covers(self, index1, index2=None):
        b, e = self.get_extent()
        if not (b <= index1 < e):
            return False
        if index2 is None:
            return True
        return b < index2 <= e

    def start_offset(self, absolute=False):
        """
        The leftmost character offset of the match.
        If absolute=True, the offset is relative to the start of the complete
        text, otherwise relative to the start of the sentence.
        """
        tseq = self.seq
        begin, end = self.get_extent()
        offs = tseq.get_normalized_offset(begin)
        if absolute:
            offs += tseq.offset
        return offs

    def end_offset(self, absolute=False):
        """
        The (exclusive) character right offset of the match.
        If absolute=True, the offset is relative to the start of the complete
        text, otherwise relative to the start of the sentence.
        """
        tseq = self.seq
        begin, end = self.get_extent()
        if end == 0:  # could be a match Match([START],0,0,)
            offs = 0
        else:
            offs = tseq.get_normalized_offset(end - 1) + tseq.lengths[end - 1]
        if absolute:
            offs += tseq.offset
        return offs

    @abstractmethod
    def get_submatches(self):
        """Get direct submatches of this match, but not recursive submatches."""
        raise NotImplementedError()

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
            if name is None or hasattr(m, 'name') and query_name_matches(name, m.name):
                result.append(m)
            for sm in m.all_submatches(name):  # recurse into submatches
                result.append(sm)
        return result

    def print_match_trace(self, indent=0):
        print("%s%s" % ((' ' * indent), self))
        for m in self.get_submatches():
            m.print_match_trace(indent=indent+2)

    # Similar to an xpath like /**/name1/**/name2/**/.../**/nameN.
    def query(self, *names) -> Iterator['Match']:
        """Used with frames, for finding in the match/submatch tree a sequence
        of matches of the given extractor names, corresponding to the sequence
        of extractor names on the RHS of a frame field definition.
        It is allowed to have matches of additional extractors in the path
        through the tree, in between the given extractor names.
        Yields the matches corresponding to the last extractor name."""
        if len(names) == 0:
            return
        if hasattr(self, 'name') and query_name_matches(names[0], self.name):
            names = names[1:]
            if len(names) == 0:
                yield self
                return
        for m in self.get_submatches():
            for sm in m.query(*names):  # recurse into submatches
                yield sm

    def matching_text(self):
        """
        The (normalized) text substring determined by the match extent.
        """
        begin, end = self.get_extent()
        if begin == end:
            return ''
        return self.seq.get_normalized_text()[self.start_offset():self.end_offset()]

    def as_json_serializable(self):
        return self.matching_text()

    def constituent_matches(self):
        """Base case for Frame method of the same name, which is recursive."""
        yield self

    def matching_lemma(self):
        lemmastrings = []
        begin, end = self.get_extent()
        for toki in range(begin, end):
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
        # Fields that contain lists. Could perhaps detect, but reasonable to enumerate.
        list_fields = [
            "submatches"
        ]
        return self._str_aux(field_to_abbr, list_fields)

    # Different kinds of matches have different fields for different kinds
    # of submatch, so this method supports a general approach to printing
    # selected fields.
    # Not all fields are generally printed by default, as that is often
    # too verbose.
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
        # TODO? May need to not directly access .begin/end.
        # Probably OK here, but check other places.
        # TODO? Consider replacing newlines in the text with \n,
        # here and in the __str__ methods of other subclasses.
        if hasattr(self, 'name'):
            return "%s([%s],%d,%d,%s%s)" % (typ, self.name, self.begin, self.end, self.matching_text(), fields)
        else:
            return "%s(%d,%d,%s%s)" % (typ, self.begin, self.end, self.matching_text(), fields)

    # TODO? This is called from vrconsole.Console.do_frame.
    # Not sure if that old code still works.
    # Note there is an overriding method in CoordMatch below.
    def operator_map(self):
        return {}

    # This seems to be uncalled anywhere.
    # TODO? The Frame ctor calls here no longer match the ctor args.
    # def frames(self):
    #     print("# Match.frames called")
    #
    #     if hasattr(self, 'frame_extractor'):
    #         yield self.frame_extractor.extract_from_match(self)
    #         return
    #
    #     omap = self.operator_map()
    #
    #     def _gen_frame(keys):
    #         if len(keys) == 0:
    #             yield Frame()
    #         else:
    #             for f in _gen_frame(keys[1:]):
    #                 key = keys[0]
    #                 val = omap[key]
    #                 if isinstance(val, list):
    #                     for v in val:
    #                         f2 = Frame(**f.fields)
    #                         f.set_field(key, v)  # TODO should be f2 here and next?
    #                         yield f
    #                 else:
    #                     f.set_field(key, val)
    #                     yield f
    #
    #     for frame in _gen_frame(list(omap.keys())):
    #         yield frame


# FAMatch was the original base class, but we moved most of the functionality
# into the new base class Match.
#
# The comment in the next paragraph predates that change.
# TODO? For now, letting the other classes continue to inherit from FAMatch,
# though Match might be better. If we change, we'll need to change docs, etc.
#
# TODO? Note that FAMatch objects are also created for token test matches,
# not just phrase expression matches.
# Since we have separate classes for FAArcMatch and CoordMatch, and those
# inherit from FAMatch, perhaps it would make sense to have a new base
# class Match, and a new match type TTMatch, and have all the leaf match
# types inherit from Match instead of FAMatch, with the possible exception
# of FAArcMatch, which may want to inherit some of FAMatch's methods.

class FAMatch(Match):
    """
    An FAMatch object adds the following member variables:
      submatches: a list of matches extracted by extractors referenced by name
    """

    def __init__(self, seq, begin, end, name=None, **kwargs):
        super().__init__(seq, begin, end, name, **kwargs)
        if not hasattr(self, "submatches"):
            self.submatches = []

    def add_submatch(self, m):
        self.submatches.append(m)

    # (Probably no strong reason for this to be a generator, probably just
    # that we don't want to expose our own list, and prefer a generator
    # to copying the list.)
    def get_submatches(self):
        """
        Generates the submatches from the internally held list field.
        """
        for m in self.submatches:
            yield m


# Note that this subclass changes the meaning of the end variable as defined
# in its superclass FAMatch, such that in FAArcMatch it's the index OF
# the end token rather than the index of the token AFTER the end token.
# Moreover, begin and end can be reversed.
class FAArcMatch(FAMatch):

    def get_extent(self):
        """
        Returns the textual extent of a match as a token index pair, with the guarantee that the first index
        will precede the second, which will be the index *after* the last token covered by the match.
        """
        # Account for FAArcMatch indices being potentially reversed.
        begin, end = self.begin, self.end
        if end < begin:
            begin, end = end, begin
        # Arc matches are end-inclusive, in contrast with other matches, which are end-exclusive
        end += 1
        return begin, end


# The fields of CoordMatch are currently somewhat haphazard, or at least
# not well documented, in terms of their intended function and meaning.
# No, actually, they're moderately well documented in docs/VRMatch.md.
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
# (But see below.)
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
#
# I will let Dayne fill in his intended meaning of "submatch" and "supermatch".
#
# TODO I notice there are a few places in the code that refer just to one or
# another of these various fields, e.g., VRManager.markup_from_token_sequences.
# This suggests some special function, contrary to what I said above.
# It's conceivable that some of those cases should be generalized,
# but either way we should document these fields better.
#
class CoordMatch(FAMatch):

    op: 'Coordinator'  # might be obsolete, but always passed to ctor

    # It's OK if some of left, right, supermatch, submatch, etc
    # are the same match.
    def __init__(self, match, **kwargs):
        """
        The "match" argument determines the extent of the CoordMatch.
        """
        super().__init__(match.seq, match.begin, match.end, **kwargs)
        self.match = match

    def __copy__(self):
        # Need to skip some attributes so they don't end up being specified
        # twice as ctor args, both positional and keyword.
        return self.__class__(self.match,
                              **{k: v for k, v in vars(self).items()
                                 if k != "match" and k != "seq" and k != "begin" and k != "end"})

    def get_extent(self):
        return self.match.get_extent()

    def get_frame(self):
        return self.match.get_frame()

    def set_frame(self, frame):
        """
        Recurses down a stack of co-extensive coordinator matches to replace the topmost frame
        with the value provided as an argument.  Returns a copy of the stack down to the replaced
        frame (sharing any match trace structures below the frame).
        """
        copy_self = copy(self)
        if isinstance(copy_self.match, Frame):
            copy_self.match = frame
        else:
            copy_self.match = copy_self.match.set_frame(frame)
        return copy_self

    def constituent_matches(self):
        return self.match.constituent_matches()

    # Compare to get_submatches of FAMatch, which generates values from
    # the submatches field. We probably don't need to be a generator.
    # The main thing is not to be recursive; all_submatches
    # (which we inherit from FAMatch) is the method that is recursive.
    # Since currently some matches are put into multiple fields,
    # this code uses a dict(id(x), x) to deduplicate.
    def get_submatches(self):
        """Non-recursive. Result includes values from all submatch attributes:
        submatches, left, right, submatch, supermatch, and (the experimental) members."""
        submatches = {}
        if hasattr(self, 'submatches') and self.submatches is not None:
            for submatch in self.submatches:
                submatches[id(submatch)] = submatch
        if hasattr(self, 'left') and self.left is not None:
            submatches[id(self.left)] = self.left
        if hasattr(self, 'right') and self.right is not None:
            submatches[id(self.right)] = self.right
        if hasattr(self, 'submatch') and self.submatch is not None:
            submatches[id(self.submatch)] = self.submatch
        if hasattr(self, 'supermatch') and self.supermatch is not None:
            submatches[id(self.supermatch)] = self.supermatch
        # "members" can be set by MergeCoordinator, which is experimental.
        if hasattr(self, 'members') and self.members is not None:
            for member in self.members:
                submatches[id(member)] = member
        return submatches.values()

    # See comments at Match's implementation of this method.
    def operator_map(self):
        opmap = dict()
        # opmap[self.match.op.label] = self.solo_text()
        label = self.op.label
        if label is None:
            if hasattr(self, "left"):
                try:
                    label = self.left.op.label
                except AttributeError:
                    pass
            if label is None and hasattr(self, "supermatch"):
                try:
                    label = self.supermatch.op.label
                except AttributeError:
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
            if isinstance(self.supermatch, CoordMatch):
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
            endpoints = (widened.left.begin, widened.left.end, widened.right.begin, widened.right.end)
            widened.begin = min(*endpoints)
            widened.end = max(*endpoints)
        if maximize:
            # Note: widen below returns widened *copies* of the submatch and
            # supermatch, which we throw away after extracting their extents.
            if hasattr(widened, 'submatch'):
                sm = self.submatch.widen(True)
                widened.begin = min(widened.begin, sm.begin, sm.end)
                widened.end = max(widened.end, sm.begin. sm.end)
            if hasattr(widened, 'supermatch'):
                sm = self.supermatch.widen(True)
                widened.begin = min(widened.begin, sm.begin, sm.end)
                widened.end = max(widened.end, sm.begin, sm.end)
        return widened

    def normalize_endpoints(self):
        """
        The NFeed coordinators group all matches having the same extents
        in their input feeds into a single output match.  The resulting
        match will have begin > end only if all of the submatches have
        that condition.
        """
        if self.begin < self.end:
            return
        if any(m for m in self.submatches if m.begin < m.end):
            self.begin, self.end = self.end, self.begin

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
            # "supermatch": "sp",
            # "left": "l",
            # "right": "r"
        }
        list_fields = [
            "submatches"
        ]
        return self._str_aux(field_to_abbr, list_fields)


# TODO This seems entirely redundant as currently used? That's because it's
# used only for matches from Select and Connects coordinators, and both have
# self.match == self.submatch, initialized from the same "pm" (patname match)
# value, and CoordMatch returns self.submatch.get_extent() for get_extent().
# OTOH, filter-type coordinators generally init with match=fm, submatch=pm.
# See also issue #28.
class DelegatedCoordMatch(CoordMatch):
    """
    A coordinator match that delegates to its submatch to determine its extent.
    For example, the extent of a select coordinator is that of its selected
    component.
    """

    def get_extent(self):
        """
        The submatch of a connects coordinator is typically an ArcMatch.
        We delegate our extent calculations to that object.
        """
        return self.submatch.get_extent()

    #def query(self, *names):
    #    return self.submatch.query(*names)


class Frame(FAMatch):
    """
    A Frame object wraps its anchor rule match, and adds a dictionary
    whose keys are field names from the LHS of VR rule language frame
    field definitions, and whose values are either single match instances
    (if there is only one value) or lists of match instances
    (if there are multiple values).
    The lists are treated as sets, and match instance equality is used
    to compare matches.
    Frame instances are treated specially in some situations, but otherwise
    are treated as instances of their anchor rule match.
    """

    def __init__(self, name, match, fields=None):
        super().__init__(match.seq, match.begin, match.end, name)
        self.match = match  # the anchor rule match
        self.fields: Dict[Text, Union['Match', List['Match']]] = \
            {k: v for k, v in fields.items()} if fields is not None else {}

    def __copy__(self):
        return Frame(self.name, self.match, self.fields)

    def get_extent(self):
        """The extent of the frame is considered to be the extent
        of the anchor rule match."""
        return self.match.get_extent()

    def get_frame(self):
        return self

    def set_frame(self, other):
        return other

    def all_submatches(self, name):
        """All matches of the given pattern name within the anchor rule match,
        (potentially including the anchor match itself); and/or matches from
        a frame field with the given name."""
        local_matches = []
        if name in self.fields:
            matches = self.fields[name]
            if isinstance(matches, list):
                local_matches.extend(matches)
            else:
                local_matches.append(matches)
        if hasattr(self.match, 'name') and query_name_matches(name, self.match.name):
            local_matches.append(self.match)
        return local_matches + self.match.all_submatches(name)

    def query(self, *names) -> Iterator['Match']:
        """
        Starting with the anchor match, successively select from that
        match matches of each named extractor from the RHS of each field,
        using the next name to select from the selected matches of the
        previous named extractor, etc.
        Initially, or after a frame extractor, the next name on the RHS
        may be a field name, in which case the subsequent RHS names
        are used to select starting from the field matches rather than
        from the anchor match.
        """
        if query_name_matches(names[0], self.name):
            names = names[1:]
            if len(names) == 0:
                yield self
                return
            # else:
            #     print(f"{self.name} matched by query(), still looking for {names}")
        if names[0] in self.fields:
            matches = self.fields[names[0]]
            names = names[1:]
            if not isinstance(matches, list):
                matches = [matches]
            for match in matches:
                if len(names) == 0:
                    yield match
                else:
                    for sm in match.query(*names):
                        yield sm
        else:
            for sm in self.match.query(*names):
                yield sm

    def start_offset(self, absolute=False):
        return self.match.start_offset(absolute)

    def end_offset(self, absolute=False):
        return self.match.end_offset(absolute)

    def matching_text(self):
        """
        The (normalized) text substring determined by the match extent.
        """
        return self.match.matching_text()

    def print_match_trace(self, indent=0):
        print("%s%s" % ((' ' * indent), self))
        self.match.print_match_trace(indent=indent+2)

    def set_field(self, field: Text, val: Union['Match', List['Match']]):
        self.fields[field] = val

    # This is as much add_match as it is add_field. Could call it add_to_field?
    def add_field(self, field: Text, val: 'Match'):
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
        """Create a MergedFrame object that combines the fields of the two frames"""
        return MergedFrame(self, other)
#        for field, value in other.fields.items():
#            if isinstance(value, list):
#                values = value
#            else:
#                values = [value]
#            for v in values:
#                self.add_field(field, v)

    def subsumes(self, other: 'Frame'):
        """
        One frame subsumes another if it contains all of the same fields
        with the same values.
        """
        for k, v in other.fields.items():
            if (k not in self.fields) or v != self.fields[k]:
                return False
        return True

    def as_json_serializable(self):
        """Represent as dict suitable for conversion to JSON string.
        Match instances are represented by their matching_text()."""
        result = dict(
            # _id=hex(id(self)),  # can be useful when debugging
            # type=type(self).__name__,    # ditto
            _type=self.name)  # TODO I'd really like to call this _name.
        for fname, values in self.fields.items():
            if isinstance(values, list):
                value_set = OrderedSet(values)  # for determinism
                value_strings = [m.as_json_serializable() for m in value_set]
                result[fname] = value_strings
            else:
                result[fname] = values.as_json_serializable()
        return result

    def as_json_serializable_with_offsets(self, source, sentence_offset, pattern):
        result = {"source": source, "pattern": pattern}
        for fname, values in self.fields.items():
            if isinstance(values, list):
                value_set = OrderedSet(values)  # for determinism
                value_strings = [{'text': m.matching_text(), 'start': m.start_offset() + sentence_offset, 'end': m.end_offset() + sentence_offset} for m in value_set]
                result[fname] = value_strings
            else:
                result[fname] = {'text': values.matching_text(), 'start': values.start_offset() + sentence_offset, 'end': values.end_offset() + sentence_offset}
        return result

    def as_json(self, indent=None):
        """Represent as JSON string."""
        return json.dumps(self.as_json_serializable(), indent=indent)

    def as_json_with_offsets(self, source, sentence_offset, pattern):
        return json.dumps(self.as_json_serializable_with_offsets(source, sentence_offset, pattern))

    def constituent_matches(self):
        """All the matches in all the fields in the frame,
        including fields in nested frames, recursively."""
        for _, values in self.fields.items():
            if not isinstance(values, list):
                values = [values]
            for v in values:
                for m in v.constituent_matches():
                    yield m

    def as_tuple(self, fields):
        def tuple_string(field):
            try:
                values = self.fields[field]
                if isinstance(values, list):
                    return "/".join(v.matching_text() for v in values)
                else:
                    return values.matching_text()
            except KeyError:
                return ""
        return tuple(tuple_string(f) for f in fields)

    # A string more like those for FAMatch and CoordMatch,
    # minimizing the loss of information.
    # It's quite verbose and probably overkill in many cases.
    # At least can rename this __str__ when debugging,
    # if not permanently in place of the above.
    def __str_debug__(self):

        to_join = []
        anchor_match = self.match
        to_join.append("_anchor_=" + str(anchor_match))
        result = dict()
        for fname, values in self.fields.items():
            if isinstance(values, list):
                value_set = OrderedSet(values)  # for determinism
                value_strings = [str(m) for m in value_set]
                result[fname] = value_strings
            else:
                result[fname] = values
        for fname, values in result.items():
            to_join.append(str(fname) + "=" + str(values))
        fields = "" if len(to_join) == 0 else ", " + ",".join(to_join)

        typ = type(self).__name__
        if hasattr(self, 'name'):
            return "%s([%s],%d,%d,%s%s)" % (typ, self.name, self.begin, self.end, anchor_match.matching_text(), fields)
        else:
            return "%s(%d,%d,%s%s)" % (typ, self.begin, self.end, anchor_match.matching_text(), fields)

    # __str__ = __str_debug__
    def __str__(self):
        return f"Frame({self.name},{self.begin},{self.end}, {self.matching_text()})"
        # return f"{type(self)}({self.name},{self.begin},{self.end}, {self.matching_text()})"  # debug
        # return f"{type(self)}({hex(id(self))},{self.name},{self.begin},{self.end}, {self.matching_text()})"  # debug


class MergedFrame(Frame):

    def __init__(self, main_frame, other_frame, fields=None):
        # Note FWIW that in both cases below, the merged frame keeps the name
        # of the main_frame, and the name of the other_frame is lost
        # (except inasmuch as the whole other_frame is stored in self).
        if fields is None:
            # Start with main_frame fields, add in other_frame_fields.
            super().__init__(main_frame.name, main_frame.match, main_frame.fields)
            for field, value in other_frame.fields.items():
                if isinstance(value, list):
                    values = value
                else:
                    values = [value]
                for v in values:
                    self.add_field(field, v)
        else:
            # Use passed-in fields.
            super().__init__(main_frame.name, main_frame.match)
            for field, value in fields.items():
                if isinstance(value, list):
                    values = value
                else:
                    values = [value]
                for v in values:
                    self.add_field(field, v)
        self.main_frame = main_frame
        self.other_frame = other_frame

    def __copy__(self):
        # This is necessary because MergedFrame cannot necessarily be
        # recreated JUST from the main_frame and other_frame, WITHOUT paying
        # attention to the CURRENT FIELDS of the MergedFrame self.
        # That's NOT the case if self has had SUBSTITUTIONS made into it.
        return MergedFrame(self.main_frame, self.other_frame, self.fields)


# In the presence of dotted import names in the match and/or query,
# it can be tricky to determine how to decide if they match.
# Similarly, it can be tricky to decide what query name to use
# when writing rules for select coordinators and frame RHS components.
#
# The current code may not handle all desirable cases ideally,
# especially in the presence of the same base rule name (i.e., not a
# dotted reference) defined in multiple managers.
#
# As a practical matter, the simplest way for a rule writer to deal
# with that is to avoid repeating the same simple name in multiple
# rules files or import scopes.
# Then one can always use an unqualified name as the query name.
def query_name_matches(qname: str, mname: Optional[str]) -> bool:
    """
    Test whether a pattern name used in a query matches a pattern name
    found in a match.
    Match names with dotted import references are stripped down to the
    same number of dotted components as found in the query name.
    """
    if mname is None:
        return False
    qname_components = qname.split('.')
    qname_count = len(qname_components)
    mname_components = mname.split('.')
    mname_count = len(mname_components)
    # Strip the mname down to the length of the qname (if longer).
    if mname_count > qname_count:
        # mname_components_orig = list(mname_components)
        mname_components = mname_components[mname_count - qname_count:]
        # if qname_components == mname_components:
        #     print(f"Stripped mname {'.'.join(mname_components_orig)} to match qname {'.'.join(qname_components)}")
    # The above code initially seemed backward to me,
    # so the code below was an experiment with doing the converse.
    # Strip the qname down to the length of the mname (if longer).
    # if qname_count > mname_count:
    #     qname_components_orig = list(qname_components)
    #     qname_components = qname_components[qname_count - mname_count:]
    #     if qname_components == mname_components:
    #         print(f"Stripped qname {'.'.join(qname_components_orig)} to match mname {'.'.join(mname_components)}")
    return qname_components == mname_components


# We briefly used this on both matches and compared the results,
# before query_name_matches was written to use instead.
def last_component_of(name: Optional[str]) -> Optional[str]:
    """Rightmost name of a possibly dotted name like import_name.rule_name,
    or None if None."""
    if name is None:
        return None
    idx = name.rfind(".")
    if idx == -1:
        return name
    else:
        return name[idx+1:]
