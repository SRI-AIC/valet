import re
from typing import Text, Tuple

from nlpcore.dbfutil import SimpleClass, GenericException
from nlpcore.tokenizer import TokenSequence
from .match import Frame


class FrameExtractor(object):

    def __init__(self, parent: 'VRManager', name: Text):
        self.parent = parent
        self.extractor_name = name
        # A dictionary whose keys are tuples of strings from the RHS 
        # of VR rule language frame slot definitions ("match_names", "mnames)),
        # and whose values ("frame_names", "fnames") are either a string
        # from the LHS of a frame slot definition, or a list of such strings.
        # frame_name = "name of slot within frame", not "name of frame".
        # TODO? Just call them slot_names and snames?
        self.fields = {}

    def requirements(self):
        return self.parent.requirements(self.extractor_name)

    def set_source_sequence(self, toks: TokenSequence):
        self.tseq = toks

    def add_frame_field(self, frame_name: Text, match_names: Tuple[Text]):
        """Add field (slot) to definition of frame (self)."""
        try:
            self.fields[match_names].append(frame_name)
        except KeyError:
            self.fields[match_names] = [frame_name]

    def matches(self):
        for m in self.parent.scan(self.extractor_name, self.tseq):
            m.frame_extractor = self
            yield m

    def scan(self, start=0):
        for m in self.parent.scan(self.extractor_name, self.tseq, start=start):
            m.frame_extractor = self
            yield m

    def extract(self):
        """Apply this frame extractor to the tseq it currently holds.
        Return a sequence-like object holding Frames."""
        result = {}
        for m in self.matches():
            frame = self.extract_from_match(m)
            if m in result:
                result[m].merge(frame)
            else:
                result[m] = frame
        return result.values()

    def extract_from_match(self, match) -> 'Frame':
        """Return a Frame for the match (which should be of this extractor)."""
        frame = Frame()
        for mnames, fnames in self.fields.items():
            fld = fnames[0]
            fnames = fnames[1:]
            added = False
            for m in match.query(*mnames):
                frame.add_field(fld, m)
                added = True
                if len(fnames) > 0:
                    fld = fnames[0]
                    fnames = fnames[1:]
            # Failed to populate one of the fields: None
#            if not added:
#                return None
        return frame


class MultiFrameExtractor(FrameExtractor):
    pass


class FrameParsingException(Exception):
    pass


class FrameExpression(SimpleClass):

    IDENTIFIER = r'(?:\w+\.)*\w+$'

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self._default('token_expression', r'(?:\w+\.)*\w+|\S')

    def tokenize(self, text):
        return re.findall(self.token_expression, text)

    def parse(self):
        self.tokens = self.tokenize(self.string)
        self.frame()
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

    def frame(self):
        self._pop_keyword('frame')
        self._pop_token('(')
        # TODO Do we need to allow import references here?
        name = self._pop_identifier(r'\w+$')
        if not name in self.parent.defined_extractors():
            raise GenericException(msg="No such extractor: %s" % name)
        self.frame_extractor = FrameExtractor(self.parent, name)
        while True:
            try:
                self._pop_token(',')
            except FrameParsingException:
                break
            self.frame_argument()
        self._pop_token(')')

    def frame_argument(self):
        # TODO Do we need to allow import references here?
        frame_name = self._pop_identifier(r'\w+$')
        self._pop_token('=')
        match_name = self._pop_identifier(self.IDENTIFIER)
        match_names = [ match_name ]
        while True:
            try:
                match_name = self._pop_identifier(self.IDENTIFIER)
                match_names.append(match_name)
            except FrameParsingException:
                break
        self.frame_extractor.add_frame_field(frame_name, tuple(match_names))
