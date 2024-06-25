import re
import traceback
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

from .annotator import NLPAnnotator, StanzaAnnotator, SpacyAnnotator, AllenSrlSpacyAnnotator
from .dbfutil import GenericException, SimpleClass


class PlainTextTokenizerWS(SimpleClass):
    """
    Tokenizer that returns as tokens runs of (ASCII) alphabetic, runs of
    (ASCII) numeric, or single other (python regex \\S) non-whitespace,
    and in addition returns runs of (ASCII) space and/or tab, and each
    newline, as tokens.
    """
    # This class has quite a bit of additional functionality.
    # For one, whitespace is tracked to support the normalize_space
    # functionality, which expands tabs to 1-8 spaces.
    # AFAICT that functionality is not currently used within nlpcore,
    # but may be used outside it.
    # For other examples, see the methods below.

    nlp_on_demand: Optional[str]

    def __init__(self, **args):
        super(PlainTextTokenizerWS, self).__init__(**args)
        # True means: don't lowercase token strings once found
        # This is independent of token_regex_ignore_case below.
        self._default('preserve_case', False)
        self._default('normalize_space', False)
        self._default('token_regex', r'[a-z]+|[0-9]+|\S|\n|[ \t]+')
        # True means: use re.I when matching against token_regex
        self._default('token_regex_ignore_case', True)
        self._default('nlp_on_demand', None)
        self.tags = {}
        self.converters = []
        # The tokenizer is informed of the NLP that is required to support
        # a VRManager's rule set.
        # Tseqs store a reference to their tokenizer, and annotators that
        # do NLP on the tseqs will check this field for what NLP to do.
        self.requirements = set()

    def add_requirements(self, reqs):
        self.requirements |= reqs

    def set_requirements(self, reqs):
        self.requirements = reqs

    def add_tags(self, tags):
        """Add the tags to the set of XML-style tags that define blocks
        which will be identified in the returned TokenSequence."""
        for tag in tags:
            self.tags[tag] = True

    def tokens_in_file(self, fname, offset=0):
        return self.tokens(self.file_contents(fname))

    def add_converter(self, pat, result):
        """Strings that match the given regex pattern will have the
        result string substituted during tokenization."""
        self.converters.append((pat, result))

    def tokens(self, string, offset=0, length=None) -> 'TokenSequence':
        """Returns TokenSequence (or subclass) instance."""

        blocks = []
        toks = []
        lengths = []
        offsets = []

        if length is None:
            length = len(string) - offset

        for tag, block, offs in self.tag_blocks(string[offset:offset + length]):
            t, l, o = self.tokens_in_block(block, offs)
            ts = len(toks)
            te = ts + len(t)
            if tag is not None:
                blocks.append((tag, ts, te))
            toks += t
            lengths += l
            offsets += o

        if self.nlp_on_demand:
            return AnnotatedTokenSequence(text=string, tokens=toks, offsets=offsets, lengths=lengths, blocks=blocks,
                                          offset=offset, length=length, nlp_on_demand=self.nlp_on_demand,
                                          tokenizer=self)

        else:
            return TokenSequence(text=string, tokens=toks,
                                offsets=offsets, lengths=lengths, blocks=blocks,
                                offset=offset, length=length)

    # Appears to search for top level begin/end XML "tag" pairs
    # defining "blocks" of text between the paired tags.
    # If there is any text outside such pairs, each is also a block
    # and is returned with a "tag" of None.
    # There is no recursion to find nested tag pairs.
    def tag_blocks(self, string):
        """
        Generates tuples of tag, block, offset.
        """

        tags = self.tags.keys()

        if len(tags) == 0:
            yield None, string, 0
            return

        tag_expr = '<(?P<tag>' + '|'.join(tags) + ')>(.*?)</(?P=tag)>'
        at = 0

        for m in re.finditer(tag_expr, string):
            tag = m.group(1)
            block = m.group(2)
            offs = m.start(0)

            if at < offs:
                yield None, string[at:offs], at

            yield tag, block, offs
            at = m.end(0)

        if at < len(string):
            yield None, string[at:], at

    # Performs tokenization.
    # Provides the normalize_space (tab stop) functionality,
    # and appears to provide for substituting fixed strings
    # for matches of optionally supplied regexes (via self.converters).
    #
    # Note the the normalize_space and conversion functionality
    # appears to bear no direct relation to the normalized token concept
    # of the TokenSequence class.
    #
    # TODO In fact, it appears to me that both of these functionalities
    # probably break the TokenSequence model to at least some degree,
    # in that the token strings, offsets, and lengths no longer match
    # the original text.
    # For example, I expect it would break the highlighting in Valet's GUI.
    def tokens_in_block(self, string, offs):

        col = 0
        toks = []
        lengths = []
        offsets = []

        def normalize_space(spaces, column):
            fragments = []
            for char in list(spaces):
                if char == '\t':
                    sc = 8 - (column % 8)
                    column += sc
                    fragments.append(' ' * sc)
                else:
                    column += 1
                    fragments.append(char)
            return ''.join(result)

        if self.token_regex_ignore_case:
            matches = re.finditer(self.token_regex, string, re.I)
        else:
            matches = re.finditer(self.token_regex, string)

        for m in matches:

            item = m.group(0)
            start = m.start(0)
            end = m.end(0)

            offsets.append(offs + start)
            lengths.append(end - start)

            if item == '\n':
                col = 0
                toks.append(item)
            elif re.match('[ \t]', item):
                if self.normalize_space:
                    newspaces = normalize_space(item, col)
                    col += len(newspaces)
                    toks.append(newspaces)
                else:
                    toks.append(item)
            else:
                converted = False
                for pat, result in self.converters:
                    if re.match(pat, item):
                        toks.append(result)
                        converted = True
                        break
                if converted:
                    continue
                if self.preserve_case:
                    toks.append(item)
                else:
                    toks.append(item.lower())

        return toks, lengths, offsets

    def tokenize(self, string) -> List[str]:
        return list(self.tokens(string))


class PlainTextTokenizer(PlainTextTokenizerWS):
    """
    Tokenizer built on PlainTextTokenizerWS that drops space/tab and newline
    tokens generated by the superclass.
    """

    def tokens(self, string, offset=0, length=None):
        toks = super(PlainTextTokenizer, self).tokens(string, offset, length)
        keepers = [ (t, o, l) for t, o, l
                    in zip(toks.tokens, toks.offsets, toks.lengths)
                    if re.match(r'\S', t) ]
        if len(keepers) > 0:
            toks.set_sequence(*zip(*keepers))
        return toks


class WordTokenizer(PlainTextTokenizer):
    """
    Tokenizer built on PlainTextTokenizer that drops tokens that do not
    start with an (ASCII) alphabetic or numeric character.
    """

    def tokens(self, string, offset=0, length=None):
        toks = super(WordTokenizer, self).tokens(string, offset, length)
        keepers = [ (t, o, l) for t, o, l
                    in zip(toks.tokens, toks.offsets, toks.lengths)
                    if re.match('[a-z0-9]', t, re.I) ]
        if len(keepers) > 0:
            toks.set_sequence(*zip(*keepers))
        return toks


# -: Legal inside both alpha and num expressions
# .: Legal inside both, elipses possible
# ,: Legal inside num
# (: Always sep
# ): Always sep
# ": Always sep
# :: Always sep
# $: Sep unless in 'C$'
# ': Part of contractions ('s or n't or 'm). Legal in alph
# /: Legal in num
# +: num prefix, alph suffix
# *: Sep (except in errors)
# ;: Sep (except in errors)
# &: Sep
# %: Sep
# =: Sep
# ?: Sep
# [: Sep
# ]: Sep
# !: Sep
# @: Sep

class CONLLTokenizer(object):

    """
    Tokenizer emulating English-language tokenization used in
    CONLL shared NER tasks.
    """

    REPEATER = r'\.\.+|\*\*+'
    AMBIG = r'[-.,]'
    UNITPUNCT = r'[()":*;&%=?\[\]!@$]'
    NUM = r'[-+]?\d+(?:[-.,/]\d+)*'
    ALPHA = r'[a-z]+$'
    WORD = r'[a-z\']+(?:[-.][a-z\']+)*\.?|c\$|s&p|m&r'
    ACRONYM = r'[a-z]\.([a-z]\.)+$'
    CAPPER = r'[A-Z]\.$'
    TOKRE = re.compile('(%s)|(%s)|(%s)|(%s)|(%s)' %
                       (WORD, NUM, REPEATER, UNITPUNCT, AMBIG),
                       re.I)

    # Abbreviations found in CONLL training data
    ABBREV = { 'vs.', 'inc.', 'st.', 'corp.', 'calif.', 'sep.', 'dr.',
               'no.', 'oct.', 'mr.', 'nov.', 'fla.', 'mrs.', 'aug.',
               'sep.', 'jan.', 'lt.', 'vol.', 'nov.', 'ill.', 'aug.',
               'wash.', 'rev.', 'no.', 'dec.',  'rabn.', 'mar.', 'govt.',
               'c$', 's&p', 'm&r',
    }

    def tokens(self, text, offset=0, length=None):
        if length is None:
            length = len(text) - offset
        toks = []
        for m in re.finditer(self.TOKRE, text[offset:offset+length]):
            tok = m.group()
            start = m.start()
            tlen = len(tok)
            if m.group(1) is None:
                toks.append((tok, start, tlen))
            elif tok.lower() in self.ABBREV:
                toks.append((tok, start, tlen))
            elif re.match(self.CAPPER, tok):
                toks.append((tok, start, tlen))
            elif re.match(self.ACRONYM, tok, re.I):
                toks.append((tok, start, tlen))
            elif re.match(self.ALPHA, tok, re.I):
                toks.append((tok, start, tlen))
            else:     # Surgery possibly required
                # Strip terminal period
                match = re.match(r'(.+)\.$', tok)
                if match is None:
                    word = tok
                    period = None
                else:
                    word = match.group(1)
                    period = '.'
                # Strip terminal contraction
                match = re.match("(.+?)('m|'s|n't|')$", word)
                if match is None:
                    contraction = None
                else:
                    word = match.group(1)
                    contraction = match.group(2)
                toks.append((word, start, len(word)))
                at = start + len(word)
                if contraction is not None:
                    toks.append((contraction, at, len(contraction)))
                    at += len(contraction)
                if period is not None:
                    toks.append((period, at, 1))
        tokseq = TokenSequence(text=text, offset=offset, length=length)
        if len(toks) > 0:
            tokseq.set_sequence(*zip(*toks))
        return tokseq


class ONTokenizer(object):
    """
    Tokenizer emulating English-language tokenization used in
    Ontonotes
    """

    URL = r'(?:https?://)?\w+(?:[-.]\w+)*\.[a-z]{2,5}(?::\d{1,5})?(?:/\S*)?'
    EMAIL = r'\w[-\w.]*@\w[-\w]*(?:\.\w[-\w]*)?\.[a-z]{2,5}'
    NUM = r'[-+]?\d+(?:[-.,/:]\d+)*(?:st|th|rd|nd)?'
    WORD = r'[-a-z\'.$]+'
    ALPHA = r'[a-z]+$'
    ACRONYM = r'[a-z]\.([a-z]\.)+$'
    CAPPER = r'[A-Z]\.$'
    STANDALONE = r'``|\'\'|"|`|--+|[?;!#\*=\+\[\]\(\)<>\{\}$%:/,]+'
    CONTRACTION = "n't|'re|'ve|'m|'ll|'d|'s"
    TOKRE = re.compile('(%s)|(%s)|(%s)|(%s)|(%s)' %
                       (URL, EMAIL, NUM, STANDALONE, WORD),
                       re.I)
    CONTRACTRE = re.compile('(.+?)(%s)$' % CONTRACTION, re.I)

    # Abbreviations found in Ontonotes training data
    ABBREV = { 'mr.', 'corp.', 'inc.', 'co.', 'ms.', 'oct.', 'etc.', 'mrs.',
               'ltd.', 'dr.', 'sen.', 'rep.', 'nov.', 'calif.', 'sept.',
               'no.', 'jr.', 'st.', 'dec.', 'tr.', 'mass.', 'conn.', 'mt.',
               'vs.', 'jan.', 'gen.', 'gov.', 'mich.', 'aug.', 'va.', 'fla.',
               'pa.', 'messrs.', 'ill.', 'feb.', 'ky.',
               'ariz.', 'cos.', 'colo.', 'prof.', 'tenn.', 'md.', 'adm.',
               'rev.', 'ore.', 'neb.', 'col.', 'ga.', 'del.', 'ind.',
               'sr.', 'wash.', 'minn.', 'mo.', 'nev.', 'bros.', 'wis.',
               'sens.', 'lt.', 'kan.', 'ft.', 'la.', 'okla.', 'ala.',
               'miss.', 'ark.', 'reps.', 'cie.', 'ph.d.', 'prop.'
    }

    SUBS = {
        '(': '-LRB-',
        ')': '-RRB-',
        '[': '-LSB-',
        ']': '-RSB-',
        '{': '-LCB-',
        '}': '-RCB-',
        '<': '-LAB-',
        '>': '-RAB-',
        '&': '-AMP-'
    }

    SUBSRE = re.compile('|'.join(re.escape(k) for k in SUBS.keys()))

    def tokens(self, text, offset=0, length=None):
        if length is None:
            length = len(text) - offset
        toks = []
#        print(text)
        for m in re.finditer(self.TOKRE, text[offset:offset+length]):
            tok = m.group()
            start = m.start()
            tlen = len(tok)
#            print(tok, start, tlen, m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))
            if m.group(5) is None:
                toks.append((tok, start, tlen))
            elif tok.lower() in self.ABBREV:
                toks.append((tok, start, tlen))
            elif re.match(self.CAPPER, tok):
                toks.append((tok, start, tlen))
            elif re.match(self.ACRONYM, tok, re.I):
                toks.append((tok, start, tlen))
            elif re.match(self.ALPHA, tok, re.I):
                toks.append((tok, start, tlen))
            else:  # Surgery possibly required
                # Strip terminal period
                match = re.match(r'(.+)\.$', tok)
                if match is None:
                    word = tok
                    period = None
                else:
                    word = match.group(1)
                    period = '.'
                # Strip terminal contraction
                match = self.CONTRACTRE.match(word)
                if match is None:
                    contraction = None
                else:
                    word = match.group(1)
                    contraction = match.group(2)
                toks.append((word, start, len(word)))
                at = start + len(word)
                if contraction is not None:
                    toks.append((contraction, at, len(contraction)))
                    at += len(contraction)
                if period is not None:
                    toks.append((period, at, 1))
        # Do ON-specific character substitutions
#        print(toks)
        toks = [ (self.SUBSRE.sub(lambda m: self.SUBS[m.group()], t), s, l) for t, s, l in toks ]
        tokseq = TokenSequence(text=text, offset=offset, length=length)
        if len(toks) > 0:
            tokseq.set_sequence(*zip(*toks))
        return tokseq


class AtomsTokenizer(SimpleClass):

    def tokenize(self, str):
        pieces = re.findall(r'(\S+?)\(\s*(\S+?)\s*,\s*(\S+?)\s*\)', str)
        return self.expand(pieces)

    def expand(self, pieces):
        isa = [ x for x in pieces if x[0] == 'isa' ]
        isa_dict = dict([ (a1, a2) for p, a1, a2 in isa ])
        normal = [self.normalize(x, isa_dict) for x in pieces if x[0] != 'isa']
        # Skip the variables
        result = [ (p, None, a2) for p, a1, a2 in isa ]
        for item in normal:
            (p, a1, a2) = item
            result.append(item)
            result.append((p, None, a2))
            result.append((p, a1, None))
            result.append((p, None, None))
        return result

    def normalize(self, tupl, isa_dict):
        (p, a1, a2) = tupl
        m = re.match('^"(.*?)"$', p)
        if m:
            p = m.group(1)
        if a1 in isa_dict:
            a1 = isa_dict[a1]
        if a2 in isa_dict:
            a2 = isa_dict[a2]
        return p, a1, a2


class TokenSequence(SimpleClass):
    """
    Utility class that represents a sequence of tokens.
    Provides six fields:
    text    - the original text which (or a portion of which) was tokenized
    offset  - starting character offset of the portion of the text that was
              tokenized
    length  - length in characters of the tokenized portion of text
    tokens  - a list of (potentially normalized) token strings
    offsets - a list of character offsets into text for the original
              unnormalized tokens
    lengths - a list of lengths of the original unnormalized tokens
    """
    # Typically a TokenSequence represents an individual sentence within
    # a larger text, but this can vary depending on the calling code.
    # I don't think any nlpcore or valetrules code currently uses the
    # normalization APIs, but an example can be found in the AMD project's
    # tablecalc code, in the CellTokenSequence class.

    text: str
    offset: int
    length: int
    tokens: List[str]
    offsets: List[int]
    lengths: List[int]

    def __init__(self, **args):
        super().__init__(**args)
        if not hasattr(self, 'tokens'):
            self.tokens = []
        if not hasattr(self, 'offsets'):
            self.offsets = []
        if not hasattr(self, 'lengths'):
            self.lengths = []

    # Typically called by tokenizer classes after filtering or otherwise
    # modifying the tokens() values from their superclass.
    def set_sequence(self, tokens: List[str], offsets: List[int], lengths: List[int]):
        """Set the three corresponding fields of self to the argument values."""
        self.tokens, self.offsets, self.lengths = tokens, offsets, lengths

    def set_tokens(self, tokens: List[str]):
        self.tokens = tokens

    def set_offsets(self, offsets: List[int]):
        self.offsets = offsets

    def set_lengths(self, lengths: List[int]):
        self.lengths = lengths

    def tokenized_text(self) -> str:
        """The original text portion that was tokenized into this TokenSequence."""
        if self.length is None:
            length = len(self.text) - self.offset
        else:
            length = self.length
        return self.text[ self.offset : self.offset + length ]

    def get_normalized_text(self) -> str:
        """This base class method implementation returns the tokenized_text()."""
        return self.tokenized_text()

    def get_normalized_offset(self, i) -> int:
        """This base class method implementation returns the value from the offsets field."""
        try:
            return self.offsets[i]
        except IndexError as e:
            # Want to be able to get a char offset for the end of
            # the string from a token index one past the last token,
            # to handle @END matches.
            if i == 0:  # better safe than sorry in case 0 tokens can happen
                return 0
            elif i == len(self.offsets):
                return self.offsets[i-1] + self.lengths[i-1]
            else:
                raise e from None

    def adjust_normalized_offsets(self, adjustments):
        """This base class method implementation is a no-op."""
        pass

    def __iter__(self) -> Iterator[str]:
        for t in self.tokens:
            yield t

    def __len__(self) -> int:
        return len(self.tokens)

    def __getitem__(self, key) -> str:
        return self.tokens[key]


# The annotations contents could be more general in principle than declared
# here, but for now I want to declare them to be what we actually use so far.
# AFAIK annotations as Set[str] come from CellTokenizer in tablecalc,
# and from AllenSrlSpacyAnnotator.
# TODO? Actually, looking at Valet's semi-experimental LearningTokenTest,
# that puts something different into the annotations, so maybe I'll want
# to back off and just use Any instead of Optional[Union[str, Set[str]]].
# That's kind of a weird case, though, so may we should keep it this way
# and just let that give warnings, so we get better checking of normal
# cases.
class AnnotatedTokenSequence(TokenSequence):
    """
    Adds a uniform way to access various annotations on the token sequence,
    such as may be provided by an external NLP library.
    """

    NLP: Optional[NLPAnnotator] = None
    nlp_on_demand: Optional[str]
    tokenizer: Any

    def __init__(self, **args):
        super().__init__(**args)
        self._default('nlp_on_demand', None)  # Optional[str]
        self._requirements_met = set()
        if not hasattr(self, 'annotations'):
            self.annotations: Dict[str, List[Optional[Union[str, Set[str]]]]] = {}
        if not hasattr(self, 'phrase_annotations'):
            self.phrase_annotations: Dict[str, List[Tuple[int, int, str]]] = {}

    def add_annotations(self, label: str, annotations: List[Optional[Union[str, Set[str]]]]):
        """
        Add a 'layer' of annotations for a token sequence.  Label is an
        arbitrary string (e.g., 'pos' to represent part of speech).
        Annotations is a list that must be the same size as the list
        of tokens.
        """
        assert len(annotations) == len(self.tokens)
        self.annotations[label] = annotations

    def has_annotations(self, label: str) -> bool:
        """
        Check whether a particular annotation layer has been added.
        """
        return label in self.annotations

    # As noted below at phrase_at(), this does not seem to be currently used,
    # so it's possible there are issues.
    def add_phrase_annotations(self, label: str, annotations: List[Tuple[int, int, str]], char_offsets=False):
        """
        Accepts annotations to phrases (token subsequences). Label is
        an arbitrary string denoting the class of annotation (e.g.,
        'ner').  Annotations is a list of tuples, each of the form
        (start, end, plabel), where start and end are token indexes
        (end is the index of the token *after* the phrase), and plabel
        is a string representing the type of phrase (e.g., "symptom").
        """

        def fst(offset):
            for toki, toffs in enumerate(self.offsets):
                if toffs == offset:
                    return toki
            raise Exception("Bad offset: %d" % offset)

        def fet(offset):
            for toki, toffs in enumerate(self.offsets):
                if toffs >= offset:
                    return toki
            return len(self.tokens)

        if char_offsets:  # Need to convert to token indexes
            annotations = [(fst(i), fet(j), p) for i, j, p in annotations]

        assert not (any(i < 0 for i, _, _ in annotations) or
                    any(j > len(self.tokens) for _, j, _ in annotations))

        self.phrase_annotations[label] = annotations

    def add_dependencies(self, dependencies):
        """
        Accepts a list of dependencies representing a parse on the set of
        tokens.
        Each dependency takes the form (from, to, label), where from and to
        are integer token indices and label is a string representing the type
        of dependency.
        (The 'to' token is the one closer to the root of the tree;
        the 'up' or 'to' direction of an edge is toward the root.)
        """
        if not hasattr(self, 'up_dependencies') and len(dependencies) > 0:
            self.up_dependencies = dict((i, []) for i in range(-1, len(self)))
            self.down_dependencies = dict((i, []) for i in range(-1, len(self)))
            self.root_tokens = set()
        for start, end, dep in dependencies:
            # This shouldn't happen, as it would mean that the root token has a syntactic parent
            if start == -1:
                raise GenericException("Sentence root can't be a syntactic child!")
            elif end == -1:
                self.root_tokens.add(start)
            else:
                self._add_dependency(start, end, dep)

    def _add_dependency(self, start, end, label):
        self.up_dependencies[start].append((end, label))
        self.down_dependencies[end].append((start, label))

    def get_up_dependencies(self, at):
        """Return list with tuples of 'to' token index and edge label."""
        self._maybe_nlp()
        if not hasattr(self, 'up_dependencies'):
            return []
        return self.up_dependencies[at]

    def get_down_dependencies(self, at):
        """Return list with tuples of 'from' token index and edge label."""
        self._maybe_nlp()
        if not hasattr(self, 'down_dependencies'):
            return []
        return self.down_dependencies[at]

    def is_root_token(self, at):
        self._maybe_nlp()
        if not hasattr(self, 'root_tokens'):
            return False
        return at in self.root_tokens

    # TODO Why is this called find_paths when in a dependency tree
    # there should only ever be one path (or possibly zero if it's
    # a polytree)?
    # Is it something that might happen when the NLP tokenization
    # differs from our own tokenization?
    def find_paths(self, start, end, include_direction=False):

        self._maybe_nlp()

        def path_search(s, e, seen=set()):

            if s in seen or s == e:
                return
            else:
                seen.add(s)

            def search_dependencies(deps, down):
                for other_ind, dep in deps[s]:
                    if not include_direction:
                        dep_str = dep
                    elif down:
                        dep_str = '\\' + dep
                    else:
                        dep_str = '/' + dep
                    if other_ind == e:
                        yield [ dep_str ]
                    else:
                        for p in path_search(other_ind, e, seen):
                            yield [ dep_str ] + p

            for path in search_dependencies(self.down_dependencies, True):
                yield path
            for path in search_dependencies(self.up_dependencies, False):
                yield path

        return [ p for p in path_search(start, end) ]

    def dependency_tree_string(self):
        """Return a multiline string visualizing the parse tree."""

        # TODO Here we're kind of assuming that both the DEPPARSE and POS
        # requirements are set in our tokenizer, which might not be
        # the case.
        # Essentially, the present function has its own requirements
        # on top of whatever the tokenizer has been informed of.
        # I call str(pos) below in case pos comes back as None,
        # and check for deps in debug_string.
        self._maybe_nlp()

        # This makes the dependency data structures very clear.
        def debug_string():
            if not hasattr(self, 'up_dependencies') or not hasattr(self, 'down_dependencies'):
                return "Raw dependencies not present"
            strings = []
            for key, dep in self.up_dependencies.items():
                strings.append(f"{key} {dep}")
            for key, dep in self.down_dependencies.items():
                strings.append(f"{key} {dep}")
            return "\n".join(strings)

        def visit(node, level, visited, strings):
            if node in visited:
                # Without SRL we don't need a visited set,
                # but here some of the SRL-derived "down" dependencies
                # actually point in the "up" direction as defined
                # by the parse dependencies. Or at least there are
                # self-links on the SRL verbs.
                raise GenericException(f"Re-visiting {node}")
            else:
                visited.add(node)
            # TODO? Add SRL info here if it exists.
            # May not matter if SRL usually results in re-visit exception.
            try:
                _, deptype = self.up_dependencies[node][0]
            except IndexError:
                deptype = "ROOT"
            pos = self.get_token_annotation("pos", node)
            # string = ("  " * (level-1) if level > 0 else "") + ("- " if level > 0 else "")
            string = ("  " * level) + "- "
            string += self.tokens[node] + " " + str(pos) + " " + deptype
            strings.append(string)
            # I'd sort these by their token index,
            # but it looks like they already are.
            for child in self.down_dependencies[node]:
                visit(child[0], level+1, visited, strings)

        try:
            # Usually there's only one root, but if NLP thinks there are
            # multiple "sentences", even despite our own sentence breaking,
            # there could be more.
            roots = sorted(self.root_tokens)
            results = []
            for root in roots:
                strings = []
                visited = set()
                visit(root, 0, visited, strings)
                results.append("\n".join(strings))
            return "\n".join(results)
        except Exception as ex:
            # Originally, in case there are corner cases we overlooked.
            # Now, with AllenSRL, we could run into RecursionError here,
            # so we added the visited list, but we still raise exception.
            # The raw dependencies are not as nice as a tree, but they
            # contain all the relevant info.
            traceback.print_exc()
            return f"Exception ({type(ex)}) when generating dependency tree string; raw dependencies are:\n" + debug_string()

    # TODO? Note FWIW there is not yet anything in valet-rules that accesses
    # this info.
    def phrase_at(self, label: str, index: int) -> Optional[Tuple[int, int, str]]:
        # TODO What if there is more than one phrase annotation starting
        # at the given index?
        return next((p for p in self.phrase_annotations[label]
                     if p[0] <= index < p[1]),
                    None)

    def get_token_annotation(self, label: str, index: int) -> Optional[Union[str, Set[str]]]:
        self._maybe_nlp()
        if label in self.annotations:
            return self.annotations[label][index]
        if label in self.phrase_annotations:
            # raise RuntimeError()  # FWIW, no valet tests exercise this branch
            p = self.phrase_at(label, index)
            if p is not None:
                return p[2]
        return None

    def has_annotation_at(self, layer_label: str, index: int, what: Union[str, Set[str]]) -> bool:
        ann = self.get_token_annotation(layer_label, index)
        if ann is None:
            return False
        if ann == what:
            return True
        if isinstance(ann, set) and what in ann:
            return True
        return False

    def set_token_annotation(self, label: str, index: int, what) -> None:
        self.annotations[label][index] = what

    def _maybe_nlp(self) -> None:
        """
        Use NLP, if available, to add annotations to this token sequence.
        This feature is controlled by the instance attribute 'nlp_on_demand'
        (default None).
        The annotations to be added are determined by this tseq's tokenizer's
        "requirements".
        This method is invoked by methods that provide access to information
        that must be generated by NLP, to ensure that the information is
        populated.
        """

        if not self.nlp_on_demand:
            return

        if self._requirements_met == self.tokenizer.requirements:
            return
        if self._requirements_met > self.tokenizer.requirements:  # DEBUG
            print("Rerunning NLP even though we already meet a strict superset of the NLP requirements.")

        self._nlp()

        # FWIW, we might meet more than just these requirements
        # if the annotator does more than the tokenizer requires
        # (e.g., see StanzaAnotator).
        # However, we may not want to count on that.
        self._requirements_met = set(self.tokenizer.requirements)

    def _nlp(self):
        """Instantiate NLPAnnotator if not already done,
        and invoke it on the present instance (of AnnotatedTokenSequence)."""
        # print("nlp_on_demand:", self.nlp_on_demand)
        if AnnotatedTokenSequence.NLP is None:
            if self.nlp_on_demand == 'stanza':
                AnnotatedTokenSequence.NLP = StanzaAnnotator()
            elif self.nlp_on_demand == 'spacy':
                AnnotatedTokenSequence.NLP = SpacyAnnotator()
            elif self.nlp_on_demand == 'allensrl':
                AnnotatedTokenSequence.NLP = AllenSrlSpacyAnnotator()
            else:
                raise GenericException(f"Unknown NLPAnnotator name specified: '{self.nlp_on_demand}'")
        AnnotatedTokenSequence.NLP.annotate(self)
