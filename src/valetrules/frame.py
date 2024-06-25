from copy import copy
import re
from typing import Dict, Iterable, Iterator, List, Mapping, \
    Optional, Text, Tuple, Union, TYPE_CHECKING

from ordered_set import OrderedSet

from nlpcore.dbfutil import GenericException

from .expression import Expression
from .extractor import Extractor
from .match import Extent, Frame, Match
if TYPE_CHECKING:
    from .manager import VRManager


class FrameExtractor(Extractor):

    # TODO? FWIW, this doesn't accept **kwargs like all the other Extractor ctors.
    def __init__(self, manager: Optional['VRManager'], extractor_name: Text):
        super().__init__(manager)
        self.extractor_name = extractor_name  # aka anchor rule name
        # A dictionary whose keys are tuples of strings from the RHS
        # of VR rule language frame field definitions ("match_names", "mnames)),
        # and whose values ("field_names", "fnames") are either a string
        # from the LHS of a frame field definition, or a list of such strings.
        self.fields: Dict[Tuple[Text, ...], Union[Text, List[Text]]] = {}

    def requirements(self, substitutions=None):
        return self.manager.requirements(self.extractor_name, substitutions=substitutions)

    def references(self):
        return OrderedSet((self.extractor_name,))

    def field_names(self) -> Tuple[Tuple[Text, ...], ...]:
        return tuple(self.fields.keys())

    def add_frame_field(self, field_name: Text, match_names: Tuple[Text, ...]):
        """Add field to definition of frame (self)."""
        try:
            self.fields[match_names].append(field_name)
        except KeyError:
            self.fields[match_names] = [field_name]

    def matches(self, seq, start=0, end=None, substitutions=None):
        return self.extract(seq, start, end, substitutions=substitutions, start_only=True)

    def scan(self, seq, start=0, end=None, substitutions=None):
        return self.extract(seq, start, end, substitutions=substitutions)

    def extract(self, seq, start=0, end=None, substitutions=None, start_only=False):
        """Apply this frame extractor to the tseq.
        Merge field data from Frame matches with the same extent
        into a single Frame.
        Return a sequence-like object holding Frames."""
        result = {}
        for m in self.manager.scan(self.extractor_name, seq, start, end, substitutions=substitutions):
            if not start_only or m.begin == start:
                frame = self.extract_from_match(m)
                if m in result:
                    result[m] = result[m].merge(frame)
                else:
                    result[m] = frame
        return result.values()

    def extract_from_match(self, match) -> 'Frame':
        """Return a Frame for the match (which should be of self.extractor_name)."""
        frame = Frame(self.name, match)
        self.extract_fields(frame, match)
        return frame

    # Not sure there are any guarantees about the order in which matches
    # that get assigned to fields with the same RHS extractor sequence
    # are generated in the first place.
    def extract_fields(self, frame, match) -> None:
        """
        # If there are multiple fields with the same RHS extractor sequence,
        # multiple matches from the sequence get assigned consecutively
        # to those fields, with the last field getting all remaining matches
        # if there are extras.
        """
        # print(f"In extract_fields for frame {frame.name} anchor match {frame.match.name}")
        for mnames, fnames in self.fields.items():
            # print(f"fnames={fnames}, mnames={mnames}")
            field = fnames[0]
            fnames = fnames[1:]
            for m in match.query(*mnames):
                # print(f"Adding match {id(m)} {m} to field {field}")
                frame.add_field(field, m)
                if len(fnames) > 0:
                    field = fnames[0]
                    fnames = fnames[1:]


# TODO? This probably needs updating due to API changes
# if it's going to be used. (There are no tests for it so far.)
# I believe the idea of this one is to have one frame rule
# "extend" another by adding more fields to it.
class ExtendedFrameExtractor(FrameExtractor):

    def __init__(self, manager, name, base_extractor: FrameExtractor):
        super().__init__(manager, name)
        self.base_extractor = base_extractor

    def requirements(self, substitutions=None):
        return self.base_extractor.requirements(substitutions=substitutions)

    def matches(self, seq):
        for m in self.base_extractor.matches(seq):
            yield m

    def scan(self, seq, start=0, end=None):
        for m in self.base_extractor.scan(seq, start=start, end=end):
            yield m

    def extract_from_match(self, match) -> Frame:
        frame = self.base_extractor.extract_from_match(match)
        self.extract_fields(frame, match)
        return frame


# Note that frame reduction has nothing to do with Regex reduction.
class FrameReducer(FrameExtractor):
    """
    The reduce operator takes a stream of matches that may be frames,
    wrap frames (in the sense of get_frame() returning a frame),
    or not wrap frames, and outputs a stream of frames.
    First, frames with the same extent are merged.
    Then, wherever frame field values that are not frames have the same extent
    as other frames, those field values are replaced with those frames,
    and the replacement frames are dropped from the output stream.
    Otherwise, non-dropped input frames become output frames.
    The effect is to embed those input frames that are implicitly referred to
    (by having the same extent) by the field values of other input frames.
    (Recall that a frame's extent is the extent of its anchor rule match.)
    """

    def __init__(self, manager, name, feed):
        super().__init__(manager, name)
        self.feed = feed

    def requirements(self, substitutions=None):
        return self.feed.requirements(substitutions=substitutions)

    @staticmethod
    def _merge(matches: Iterable[Match]) -> Mapping[Extent, Frame]:
        """Does the merging described in the class docstring.
        Merging creates a new frame so that cached frames are not modified.
        Unmerged frames are copied too so that subsequent linking doesn't
        modify a possibly cached frame.
        Returns dict of frames by extent."""
        frames = {}
        for m in matches:
            extent = m.get_extent()
            frame = m.get_frame()
            if frame is not None:
                try:
                    # tmp = frames[extent]
                    frames[extent] = frames[extent].merge(frame)
                    # print(f"FrameReducer.merge merged frame {hex(id(tmp))} and {hex(id(frame))} giving {hex(id(frames[extent]))}")
                except KeyError:
                    frames[extent] = copy(frame)
                    # print(f"FrameReducer.merge copied frame {hex(id(frame))} giving {hex(id(frames[extent]))}")
                    # print(f"FrameReducer.merge copied frame {frame.as_json()} giving {frames[extent].as_json()}")
        return frames

    @staticmethod
    def _link(frames: Mapping[Extent, Frame]) -> None:
        """Does the replacement described in the class docstring."""

        def substitute(frames, frame):
            """
            Substitute frames from "frames" into direct and recursive field
            values of "frame", when the field value is not already a frame.
            "frame" is not necessarily one of "frames".
            """
            extent = frame.get_extent()
            for fname in frame.fields.keys():
                values = frame.fields[fname]
                new_values = []
                for v in (values if isinstance(values, list) else (values,)):
                    vextent = v.get_extent()
                    vframe = v.get_frame()
                    if vframe is not None:
                        new_values.append(v)  # keep original v
                        substitute(frames, vframe)  # recurse
                    elif vextent in frames and vextent != extent:  # don't substitute frame into field of itself or of a contained frame
                        # print(f"Substituting frame {frames[vextent].as_json()} for '{v.matching_text()}' in {frame.as_json()}")
                        new_values.append(frames[vextent])  # substitute coextensive frame
                    else:
                        new_values.append(v)  # keep original v
                frame.fields[fname] = (new_values if isinstance(values, list)
                                       else new_values[0])

        for frame in frames.values():
            # Substitute frames from "frames" into the fields of this frame and
            # any recursively contained frames, whether originally contained
            # or already substituted.
            substitute(frames, frame)

    @staticmethod
    def _get_subframes(frames) -> OrderedSet[int]:
        """Return the python id's of those frames that are not subframes of
        other frames, i.e., are not embedded in a field of another frame."""
        frames = dict((id(f), f) for f in frames)
        subframes = OrderedSet()
        visited = set()

        def note_subframes(frame):
            """Record ids of any subframes of 'frame' into 'subframes'."""
            for values in frame.fields.values():
                for v in (values if isinstance(values, list) else (values,)):
                    vid = id(v)
                    if isinstance(v, Frame) and vid not in visited:
                        # The as_json call can give RecursionError if there
                        # are cycles, as they won't have been broken yet.
                        # But it's more informative than the next if not.
                        # print(f"Noting frame {v.as_json()} as a subframe of {frame.as_json()}")
                        # print(f"Noting frame {hex(id(v))} as a subframe of {hex(id(frame))}")
                        subframes.add(vid)
                        visited.add(vid)
                        note_subframes(v)

        for frame in frames.values():
            # print(f"Noting subframes of {hex(id(frame))}")
            note_subframes(frame)

        return subframes

    # Cyclic references, or multiple non-cyclic references,
    # tend to happen when there are phrase matches that
    # unfortunately span different parts of the parse tree,
    # so multiple downward links point to the same extent
    # instead of what should be different extents.
    @staticmethod
    def _break_reference_cycles(frame):

        # Used as a stack. Originally we kept adding to a set,
        # but that unnecessarily breaks subsequent but non-cyclic references.
        # We could use a set here now, and remove instead of popping,
        # potentially improving the efficiency of the check
        #   id(thing) in visited
        # from O(N) to O(1), but a list is clearer and probably
        # not that much slower in practice.
        visited = []

        def _break(thing):
            if not isinstance(thing, Frame):
                return thing
            elif id(thing) in visited:
                # Break cyclic reference to frame already on stack;
                # refer to non-frame match instead.
                return thing.match
            else:
                visited.append(id(thing))
                for field in list(thing.fields.keys()):
                    values = thing.fields[field]
                    if isinstance(values, list):
                        thing.fields[field] = [_break(v) for v in values]
                    else:
                        thing.fields[field] = _break(values)
                visited.pop()
                return thing

        return _break(frame)

    # TODO? start_only was added to superclass method, compiler warns this signature differs.
    def extract(self, seq, start=0, end=None, substitutions=None) -> Iterator[Frame]:
        if start != 0 or (end is not None and end != len(seq)):
            raise GenericException(msg=f"Frame reduce operation not implemented on token subsequence")

        # Get all the feed matches.
        matches: List[Match] = list(self.feed.scan(seq, substitutions=substitutions))

        # First copy and merge contained frames with the same extent.
        frames: Mapping[Extent, Frame] = self._merge(matches)

        # Now we only have frames, and none with the same extent.
        # Do the linking (substitution).
        # print(f"Frames to be linked are {[hex(id(frame)) for frame in frames.values()]}")
        self._link(frames)

        # Find the frames that became subframes.
        # (Could we just return those from _link?
        # Or the ones that didn't?)
        subframes: OrderedSet[int] = self._get_subframes(frames.values())

        # Yield those that did not.
        for frame in frames.values():
            if id(frame) not in subframes:
                yield self._break_reference_cycles(frame)


class MultiFrameExtractor(FrameExtractor):
    pass


class FrameParsingException(Exception):
    pass


# frame_expression -> frame_op | reduce_op
# frame_op -> 'frame', '(', extractor_name, field_spec, [ ',' field_spec, ...] ')'
# field_spec -> field_name, '=', field_selector
# reduce_op  -> 'reduce', '(', frame_name, ')'
class FrameExpression(Expression):

    IDENTIFIER = r'(?:\w+\.)*\w+$'
    OPERATOR = r'frame|reduce$'

    token_expression: str
    tokens: list

    def __init__(self, expr: str, manager: Optional['VRManager'], **kwargs):
        super().__init__(expr, manager, **kwargs)
        self._default('token_expression', r'(?:\w+\.)*\w+|\S')
        self.frame_extractor: FrameExtractor = None

    def tokenize(self, expr):
        return re.findall(self.token_expression, expr)

    def parse(self) -> FrameExtractor:
        self.tokens = self.tokenize(self.expr)
        self.frame_expression()  # creates and sets self.frame_extractor
        if len(self.tokens) > 0:
            raise FrameParsingException("Extra tokens in input starting with '%s'" % self.tokens)
        return self.frame_extractor

    def _pop_token(self, expected) -> Text:
        tok = self.tokens.pop(0)
        if tok != expected:
            self.tokens.insert(0, tok)
            raise FrameParsingException("Expected '%s', got '%s'" % (expected, tok))
        return tok

    def _pop_identifier(self, regex) -> Text:
        tok = self.tokens.pop(0)
        if not re.match(regex, tok):
            self.tokens.insert(0, tok)
            raise FrameParsingException("Token '%s' does not match expected form: %s" % (tok, regex))
        return tok

    def _pop_keyword(self, *options) -> Text:
        tok = self.tokens.pop(0)
        if tok not in options:
            self.tokens.insert(0, tok)
            raise FrameParsingException("Token '%s' not one of %s" % (tok, options))
        return tok

    def frame_expression(self) -> None:
        op = self._pop_identifier(self.OPERATOR)
        if op == 'frame':
            self.frame()
        else:  # op == 'reduce'
            self.reduce()

    def frame(self) -> None:
        self._pop_token('(')
        anchor_name = self._pop_identifier(self.IDENTIFIER)
        # Doesn't this require the anchor rule to be defined first?
        # Isn't that a departure from our usual practice?
        # Doesn't seem necessary; commenting it out.
        # if not self.manager.extractor_is_defined(anchor_name):
        #     raise GenericException(msg="No such extractor: %s" % anchor_name)
        self.frame_extractor = FrameExtractor(self.manager, anchor_name)
        self.frame_arguments()

    def frame_arguments(self) -> None:
        while True:
            try:
                self._pop_token(',')
            except FrameParsingException:
                break
            self.frame_argument()
        self._pop_token(')')

    def reduce(self) -> None:
        self._pop_token('(')
        name = self._pop_identifier(self.IDENTIFIER)
        base_extractor, type_, _ = self.manager.lookup_extractor(name)
        self.frame_extractor = FrameReducer(self.manager, name, base_extractor)
        self._pop_token(')')

    def frame_argument(self) -> None:
        field_name = self._pop_identifier(r'\w+$')
        self._pop_token('=')
        match_name = self._pop_identifier(self.IDENTIFIER)
        match_names = [match_name]
        while True:
            try:
                match_name = self._pop_identifier(self.IDENTIFIER)
                match_names.append(match_name)
            except FrameParsingException:
                break
        self.frame_extractor.add_frame_field(field_name, tuple(match_names))
