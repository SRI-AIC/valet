
import os.path
import itertools
from typing import Iterable, Tuple, Union, Iterator
from collections import defaultdict, deque

from nlpcore.tokenizer import PlainTextTokenizer
from nlpcore.sentencer import Sentencer
from nlpcore.dbfutil import SimpleClass

from .tokentest import MembershipTokenTest, LearningTokenTest
from .fa import SequenceStartFiniteAutomaton, SequenceEndFiniteAutomaton, LexiconMatcher, ParseRootFiniteAutomaton
from .regex import Regex
from .statement import *
import json

"""
Provides the VRManager class, which can read a pattern file and build up 
an interconnected set of FiniteAutomatons and other classes that can be used 
to recognize the language specified by the patterns.

The primary role of the VRManager is to hold an interrelated set of patterns, 
allowing them to cross-reference each other, and to to provide operations 
for matching token sequences against the set of patterns.

Main operations are:
- parseFile - read pattern file, build FAs
- match - match a pattern against token sequence at specified starting point
- search - match a pattern against token sequence at any starting point from specified one on
- scan - match a pattern against token sequence, continuing...
"""

class VRManager(SimpleClass):

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self._default('exception_on_redefinition', True)
        self._default('verbose', False)  # really verbose_imports
        self._default('caching', True)
        self.tokr = PlainTextTokenizer(preserve_case=True)
        self.forget()

    def forget(self):
        self.cached_tseq = None
        if self.caching:
            self.cache = {}
        else:
            self.cache = None
        # self.imported_files = {}
        self.fas = {
            'START': SequenceStartFiniteAutomaton(),
            'END': SequenceEndFiniteAutomaton(),
            'ROOT': ParseRootFiniteAutomaton()
        }
        self.fa_expressions = {}
        self.fa_lexicon_imports = {}
        self.ifas = {}
        self.tests = {}
        self.test_expressions = {}
        self.imports = {}
        self.import_expressions = {}
        self.coords = {}
        self.coord_expressions = {}
        self.dep_fas = {}
        self.dep_fa_expressions = {}
        self.frames = {}
        self.frame_expressions = {}
        #        self.define_table_test('sharp', ['#'])

    def set_embedding(self, embedding):
        self.embedding = embedding

    def read_embedding(self, embedding_file):
        from .extml import Embedding
        self.set_embedding(Embedding(embedding_file))

    def set_expander(self, expander):
        self.expander = expander

    def read_expander(self, term_expansion_directory):
        from nlpcore.term_expansion import TermExpansion
        expander = TermExpansion(input_directory=term_expansion_directory)
        expander.read_term_expansion_data()
        self.set_expander(expander)

    def parse_file(self, fname, verbose=None):
        """Parse file with patterns, represent as internal set of FAs."""
        if verbose is not None:
            print("VRManager.parse_file 'verbose' argument is deprecated; pass to ctor instead")
            self.verbose = verbose
        self.pattern_file = fname
        block = self.file_contents(fname)
        self.parse_block(block)

    def parse_block(self, block):
        parser = StatementParser(block)
        for statement in parser.statements():
            try:
                statement.register(self)
            except:
                import traceback
                traceback.print_exc()

    def register(self, region):
        # TODO: Implement
        if isinstance(region, MacroRegion):
            return

        if isinstance(region, TestExpressionRegion):
            tab, etab = self.tests, self.test_expressions
        elif isinstance(region, PhraseExpressionRegion):
            tab, etab = self.fas, self.fa_expressions
        elif isinstance(region, ImportRegion):
            tab, etab = self.imports, self.import_expressions
        elif isinstance(region, CoordRegion):
            tab, etab = self.coords, self.coord_expressions
        elif isinstance(region, DependencyRegion):
            tab, etab = self.dep_fas, self.dep_fa_expressions
        elif isinstance(region, FrameRegion):
            tab, etab = self.frames, self.frame_expressions
        else:
            raise ValueError("Unknown region type: %s" % region)

        name = region.spec()
        self.raise_if_defined(name)
        tab[name] = region.interpret(self)
        etab[name] = region.expression()

    # TODO? This code has a lot of duplication with TokenTestExpression.atom() 
    # in tokentest.py.
    def import_token_tests(self, name, expr):
        m = re.match('([cj]?){(.*)}(s?i?s?)$', expr)
        isfile = m.group(1)
        fname = m.group(2)
        insens = m.group(3) and 'i' in m.group(3)
        stemming = m.group(3) and 's' in m.group(3)
        subm = VRManager(verbose=self.verbose)
        # TODO Avoid duplicate messages from both here and resolve_import_path.
        # Here we also show the type; maybe not that important.
        if isfile:
            if isfile == 'c':
                (labelfile,clusterfile) = [self.resolve_import_path(x.strip()) for x in fname.partition(";") if x != ";"]
                with open(labelfile) as infile:
                    labels = dict(enumerate([x.strip() for x in infile]))
                memberships = defaultdict(set)
                if self.verbose:
                    print("VR: Importing cluster file %s" % clusterfile)
                with open(clusterfile) as infile:
                    for (number,line) in enumerate(infile):
                        cluster = line.strip()
                        memberships[cluster].add(labels[number])
                for (cluster,members) in memberships.items():
                    subm.tests[cluster] = MembershipTokenTest(members=members, case_sensitive=not insens, stemming=stemming, name=cluster)
            elif isfile == 'j':
                if self.verbose:
                    print("VR: Importing json file %s" % fname)
                with open(fname) as infile:
                    membmaps = json.load(infile)
                for (cluster, members) in membmaps.items():
                    subm.tests[cluster] = MembershipTokenTest(members=members, case_sensitive=not insens, stemming=stemming, name=cluster)
        else:
            path = self.resolve_import_path(fname)
            if self.verbose:
                print("VR: Importing token list file %s" % path)
            with open(path) as infile:
                members = [x.strip() for x in infile]
            subm.tests[name] = MembershipTokenTest(members=set(members), case_sensitive=not insens, stemming=stemming, name=name)
        return subm

    def import_file(self, fname):
        path = self.resolve_import_path(fname)
        # This kind of caching can lead to confusing results, since Valet expressions can import from data
        # files.  If the expressions that import those files don't change, but the data files do, behavior
        # will be incorrect.
        #mtime = os.path.getmtime(path)
        #try:
        #    subm, imported_mtime = self.imported_files[path]
        #    if mtime <= imported_mtime:
        #        return subm
        #except KeyError:
         #   pass
        subm = VRManager(verbose=self.verbose)
        # if self.verbose:
        #     print("VR: Importing %s" % path)
        subm.parse_file(path)
        # self.imported_files[path] = (subm, mtime)
        return subm

    def import_lexicon_matcher(self, fname, case_insensitive, is_csv, target_column):
        path = self.resolve_import_path(fname)
        return LexiconMatcher(path, case_insensitive, is_csv, target_column, self)

    def resolve_import_path(self, fname):
        """Returns resolved path. 
        Throws exception if unable to resolve to an existing file."""
        # First things first.  Resolve fname if not absolute.
        import pkg_resources
        path = None
        resolution = None
        if os.path.abspath(fname) == fname:  # Absolute path
            path = fname
            resolution = "absolute"
        elif os.path.exists(fname):  # Resolvable from cwd
            path = os.path.abspath(fname)
            resolution = "cwd"
        else:
            # Relative to directory containing current pattern file
            cur_path = None
            if hasattr(self, 'pattern_file'):
                mydir = os.path.dirname(self.pattern_file)
                cur_path = os.path.join(mydir, fname)
            if cur_path is not None and os.path.exists(cur_path):
                path = cur_path
                resolution = "parent"
            # The vrules file is one of the built-ins.
            elif pkg_resources.resource_exists(__name__, "data/%s" % fname):
                path = pkg_resources.resource_filename(__name__, "data/%s" % fname)
                resolution = "builtin"
        if path is None or not os.path.exists(path):
            msg = "Can't resolve import path '%s' (resolution='%s', path='%s')" % (fname, resolution, path)
            raise GenericException(msg=msg)
        else:
            if self.verbose:
                print("Resolved import path '%s' (resolution='%s', path='%s')" % (fname, resolution, path))
        return path

    def model_path(self, model_name):
        """
        Return path for saving learned model.
        """
        mydir = os.path.dirname(self.pattern_file)
        return os.path.join(mydir, model_name)

    def raise_if_defined(self, name):
        """Raise exception if name is already used as a pattern name."""
        if not self.exception_on_redefinition:
            return
        _, type = self.lookup_extractor(name, fail_if_undef=False)
        if type is not None:
            raise GenericException(msg="'%s' is already defined as a %s expression" % (name, type))

    # def define_table_test(self, name, members, case_insensitive=False):
    #     test = MembershipTokenTest(table=dict((x, True) for x in members),
    #                                case_sensitive = not case_insensitive)
    #    self.tests[name] = test

    # def define_substring_test(self, name, substr, case_insensitive=False):
    #     test = SubstringTokenTest(substring=substr)
    #     self.tests[name] = test

    def test_defined(self, name):
        return name in self.tests

    # For making nice error messages.
    extractor_type_to_long_name_map = {
        'test': 'token test',
        'fa': 'phrase',
        'dep_fa': 'parse',
        'coord': 'coordinator',
        'frame': 'frame'
    }
    # Started as a staticmethod, but caller can't import this module 
    # due to circular reference.
    def extractor_type_to_long_name(self, type_):
        return VRManager.extractor_type_to_long_name_map[type_]

    def lookup_extractor(self, name, fail_if_undef=True):
        """Return tuple with extractor object and (quasi-)type name 
        (coord, fa, dep_fa, frame, test)."""
        m = re.match(r'(\w+)\.(.*)', name)
        if m:
            mgr = self.imports[m.group(1)]
            return mgr.lookup_extractor(m.group(2))
        if name in self.coords:
            return self.coords[name], 'coord'
        elif name in self.fas:
            fa = self.fas[name]
            if isinstance(fa, Regex):
                fa = self.fas[name] = fa.compile()
                fa.name = name
            return fa, 'fa'
        elif name in self.dep_fas:
            fa = self.dep_fas[name]
            if isinstance(fa, Regex):
                fa = self.dep_fas[name] = fa.compile()
                fa.name = name
            return fa, 'dep_fa'
        elif name in self.frames:
            return self.frames[name], 'frame'
        elif name in self.tests:
            return self.tests[name], 'test'
        elif not fail_if_undef:
            return None, None
        else:
            raise GenericException(msg="Pattern name not found: %s" % name)

    def lookup_pattern(self, name):
        """Return tuple with pattern definition delimiter (~, ->, ^, $, :) 
        and expression body."""
        m = re.match(r'(\w+)\.(.*)', name)
        if m:
            # TODO: Need to get an example file of patterns so we can be sure this does what is intended.
            mgr = self.imports[m.group(1)]
            return mgr.lookup_pattern(m.group(2))
        if name in self.coords:
            # ~
            return '~', self.coord_expressions[name]
        elif name in self.fas:
            # ->
            return '->', self.fa_expressions[name]
        elif name in self.dep_fas:
            # ^
            return '^', self.dep_fa_expressions[name]
        elif name in self.frames:
            # $
            return '$', self.frame_expressions[name]
        elif name in self.tests:
            # :
            return '#', self.test_expressions[name]
        else:
            raise GenericException(msg="Pattern name not found: %s" % name)

    def lookup_learning_test(self, name):
        extractor, type_ = self.lookup_extractor(name, fail_if_undef=False)
        if extractor is None:
            return None
        if type_ != 'test':
            return None
        if not isinstance(extractor, LearningTokenTest):
            return None
        return extractor

    @staticmethod
    def peek_and_replace(iterator: Iterator["T"]) -> Tuple[Union["T", None], Iterable["T"]]:
        """
        Peek and replace an item from an iterator

        :param iterator an iterator such as a generator
        :return Returns the next item or None if there isn't a next item as well as an iterable that is effectively the
            same as the original
        """
        nxt = None
        try:
            nxt = next(iterator)
        except Exception as e:
            if type(e) is StopIteration:
                pass
            else:
                raise e
        if nxt:
            iterator = itertools.chain([nxt], iterator)
        else:
            iterator = itertools.chain([], iterator)
        return nxt, iterator

    def caching(func):
        def wrapper(self, name, ext, type_, toks, start=0, end=None):
            if self.cache is not None:
                tseq_id = id(toks)
                if tseq_id != self.cached_tseq:
                    self.cache = {}
                    self.cached_tseq = tseq_id
                key = (func, name, type_, start, end)
                try:
                    hit = self.cache[key]
                except KeyError:
                    hit = None
                if hit is None:
                    hit = list(func(self, name, ext, type_, toks, start=start, end=end))
                    self.cache[key] = hit
                for m in hit:
                    yield m
            else:
                for m in func(self, name, ext, type_, toks, start=start, end=end):
                    yield m
        return wrapper

    # TODO? We may ultimately want to accept a bounds args here.
    # E.g., in MatchCoordinator.scan, passing bounds to VRManager.scan 
    # would let phrase patterns implement the alternate START/END semantics.
    # FAs and ArcFAs already accept a bounds arg.
    # Token tests and coordinators currently do not.
    # OTOH, some of our current thinking is that we may not need a bounds arg, 
    # because we'll always want the bounds to be either the start/end args, 
    # or 0/len(toks), and we may have separate SSTART/SEND (nominal names) 
    # predefined patterns to implement that semantics.
    @caching
    def _scan(self, name, ext, type_, toks, start=0, end=None):
        """
        Generate a sequence of *all* matches in the token sequence 
        within the indicated start/end range.
        """
        if type_ == 'coord':
            # TODO? Would it make sense to try to make these scan methods 
            # more consistent? E.g., always pass the toks to the scan method?
            ext.set_source_sequence(toks)
            gen = ext.scan(start=start, end=end)
        elif type_ == 'fa' or type_ == 'dep_fa':
            gen = ext.scan(toks, start, end)
        elif type_ == 'frame':
            if start != 0 or end != None:
                raise GenericException(msg="Frames cannot scan from/to an index != 0/len. Frame name = %s, implementation is %s" % (name, ext))
            ext.set_source_sequence(toks)
            # gen = ext.scan(start=start, end=end)
            gen = ext.scan()
        elif type_ == 'test':
            gen = ext.scan(toks, start, end)
        else:
            raise GenericException(msg="Unknown pattern type: %s" % type_)

        for m in gen:
            # Note FWIW this is one key place where match names are assigned. 
            # (It seems like coordinators try to name matches after themselves 
            # when they create them, but usually they don't have names 
            # themselves, although I've seen exceptions.)
            # Matches of internal subexpressions don't get to here and 
            # don't get named (name = None).
            m.name = name
            yield m

    def match(self, patname, toks, start=0, end=None):
        """
        Return the *longest* match encountered starting (only) at the 
        start token, within the indicated start/end range, or None if none.
        """
        ext, type_ = self.lookup_extractor(patname)
        match = None
        for m in self._scan(patname, ext, type_, toks, start, end):
            if m.start != start:
                return match
            if match is None or m.end > match.end:
                match = m
        return match

    # This is used for "callouts" in FA and ArcFA.
    def matches(self, patname, toks, start=0, end=None, bounds=None):
        """
        Looks up an extractor for 'patname' and delegates to that extractor's 
        matches() method, optionally doing cache lookup.
        """
        ext, type_ = self.lookup_extractor(patname)
        for m in self._matches(patname, ext, type_, toks, start, end):
            yield m

    @caching
    def _matches(self, name, ext, type_, toks, start=0, end=None):
        if type_ == 'frame':
            raise GenericException(msg="Frames do not implement the 'matches' method")
        for m in ext.matches(toks, start, end):
            # Note FWIW this is one key place where match names are assigned. 
            m.name = name
            yield m

    def search(self, patname, toks, start=0, end=None):
        """
        Return the *first* match encountered 
        within the indicated start/end range, or None if none.
        """
        ext, type_ = self.lookup_extractor(patname)
        for m in self._scan(patname, ext, type_, toks, start, end):
            return m
        return None

    # Be aware that the method names scan/search/match/matches are widely used 
    # across classes including VRManager and the various extractor classes 
    # like TokenTest, {Arc,}FiniteAutomaton, coordinator classes, and Frame, 
    # but often with subtle differences in their semantics. 
    def scan(self, patname, toks, start=0, end=None):
        """
        Generate a sequence of *all* matches in the token sequence 
        within the indicated start/end range.
        """
        ext, type_ = self.lookup_extractor(patname)
        for m in self._scan(patname, ext, type_, toks, start, end):
            yield m

    def present(self, patname, text, useSentencer=False):
        if not useSentencer:
            toks = self.tokr.tokens(text)
            return self.search(patname, toks)
        #TODO:  Test and refactor this code.  Hastily added to assist in an evaluation
        sentr = self.get_sentr()
        for sentence in sentr.sentences(text):
            toks = sentence.tokens()
            result = self.search(patname, toks)
            if result:
                return result
        return False

    def get_sentr(self):
        if hasattr(self,"sentr"):
            return self.sentr
        else:
            self.sentr = Sentencer(blank_line_terminals=True, tokenizer=self.tokr, skip_initial_regex='[^a-zA-Z]+')
            return self.sentr

    def markup_from_token_sequences(self, patname, tseqs, trim=False):
        matches = []
        submatches = []
        for tseq in tseqs:
            lastm = None
            for m in sorted(list(self.scan(patname, tseq))):
                if lastm is None or not lastm.overlaps(m):
                    matches.append(m)
                    if hasattr(m, "submatch"):
                        matches.append(m.submatch)
                        submatches.append(m.submatch)
                lastm = m
        text = tseqs[0].text
        for m in reversed(list(matches)):
            start = m.start_offset(absolute=True)
            end = m.end_offset(absolute=True)
            if m not in submatches:
                text = text[0:start] + ' >>> ' + text[start:end] + ' <<< ' + text[end:]
            else:
                text = text[0:start] + ' {{{ ' + text[start:end] + ' }}} ' + text[end:]
        if trim:
            matchers = [line for line in re.split('\n', text) if re.search(r'>>>|<<<|{{{|\}\}\}', line)]
            text = '\n'.join(matchers)
        return text

    def markup_from_token_sequence(self, patname, tseq, trim=False):
        return self.markup_from_token_sequences(patname,[tseq], trim)

    def snippets_from_token_sequence(self, patname, tseq, context=3):
        for m in self.scan(patname, tseq):
            start_offset = m.start_offset()
            end_offset = m.end_offset()
            text = tseq.text
            start = m.begin - context
            if start < 0:
                start = 0
            end = m.end + context
            if end > len(tseq):
                end = len(tseq)
            snippet = text[tseq.offsets[start]:start_offset]
            snippet += " >>> " + text[start_offset:end_offset] + " <<< "
            snippet += text[end_offset:tseq.offsets[end-1] + tseq.lengths[end-1]]
            yield snippet

    def extract_offsets_from_token_sequence(self, patname, toks):
        matches = self.scan(patname, toks)
        phrases = []
        for m in matches:
            s = m.begin
            e = m.end
            start = toks.offsets[s]
            end = toks.offsets[e-1] + toks.lengths[e-1]
            phrases += [(start,end)]
        return patname, phrases

    def markup(self, patname, text):
        """Mark up text by adding annotations for matches of the 'patname' expression
        (and sub- or descendant constituent expressions). Annotations are in
        >>> <<< brackets and take the form <type>(match);
        for example, >>> <noun_phrase>(the organization) <<<"""
        toks = self.tokr.tokens(text)
        return self.markup_from_token_sequence(patname, toks)

    def normalized_extraction(self, toks, match):
        fragment = match.matching_text()
        fragment = re.sub(r'\s+', ' ', fragment)
        return fragment #+ "\n\t" + str(toks)
        #return str(match) + ":" + fragment

    def get_frame(self, toks, match):
        return toks.find_paths(match.begin, match.end)

    def frame_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.get_path(toks, m)
            else:
                return None
        else:
            m = self.scan(patname, toks)
            return [ str((self.normalized_extraction(toks,x), self.get_path(toks, x))) for x in m ]

    def frame_from_token_sequences(self, patname, toks, first_only=False):
        paths = []
        for seq in toks:
            paths += self.path_from_token_sequence(patname, seq,first_only)
        return paths

    def get_path(self, toks, match):
        #return toks.find_paths(match.begin,match.end)
        #Note:  find paths uses inclusive end, match uses exclusive end
        return toks.find_paths(match.begin,match.end -1)

    def get_pos(self, toks, match):
        return [(tok,pos) for (tok,pos) in zip(toks,toks.annotations["pos"])]

    def pos_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.get_pos(toks, m)
            else:
                return None
        else:
            m = self.scan(patname, toks)
            return [ str((self.normalized_extraction(toks,x), self.get_pos(toks, x))) for x in m ]

    def pos_from_token_sequences(self, patname, toks, first_only=False):
        paths = []
        for seq in toks:
            paths += self.pos_from_token_sequence(patname, seq,first_only)
        return paths

    def path_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.get_path(toks, m)
            else:
                return None
        else:
            m = self.scan(patname, toks)
            return [ str((self.normalized_extraction(toks,x), self.get_path(toks, x))) for x in m ]

    def path_from_token_sequences(self, patname, toks, first_only=False):
        paths = []
        for seq in toks:
            paths += self.path_from_token_sequence(patname, seq,first_only)
        return paths

    def extract_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.normalized_extraction(toks, m)
            else:
                return None
        else:
            m = self.scan(patname, toks)
            return [ self.normalized_extraction(toks, x) for x in m ]

    def extract_from_token_sequences(self, patname, toks, first_only=False):
        extractions = []
        for seq in toks:
            extractions += self.extract_from_token_sequence(patname, seq,first_only)
        return extractions

    def conll_from_token_sequence(self, extractor_names, tseq):
        tags = []
        matches = []
        for ename in extractor_names:
            matches.extend(self.scan(ename, tseq))
        matches = sorted(matches)
        toki = 0
        for match in matches:
            name = match.name
            start = match.begin
            end = match.end
            if toki > start:
                continue
            while toki < start:
                tags.append((tseq[toki], 'O'))
                toki += 1
            tags.append((tseq[start], "B-%s" % name))
            toki += 1
            while toki < end:
                tags.append((tseq[toki], "I-%s" % name))
                toki += 1
        while toki < len(tseq):
            tags.append((tseq[toki], 'O'))
            toki += 1
        return "\n".join("%s\t%s" % (tag[0], tag[1]) for tag in tags)

    def expanded_conll_from_token_sequence(self, extractor_names, tseq) -> Iterable[str]:
        """

        Args:
            extractor_names:
            tseq:

        Returns:

        """
        matches = defaultdict(list)
        for ename in extractor_names:
            matches[ename] = self.scan(ename, tseq)
        tag_queues = [deque() for i in range(len(matches))]
        for i, tok in enumerate(tseq):
            i_tags = []
            for m_idx, ename in enumerate(extractor_names):
                tag_queue = tag_queues[m_idx]
                if tag_queue:  # a match continues
                    cur_tag = tag_queue.pop()
                else:
                    match, m_matches = self.peek_and_replace(matches[ename])
                    matches[ename] = m_matches
                    if match is not None:
                        if match.begin == i:  # a starts match
                            cur_tag = f"B-{match.name}"
                            for j in range(match.end - (match.begin + 1)):  # fill matches to continue
                                tag_queues[m_idx].appendleft(f"I-{match.name}")
                            _ = next(matches[ename])  # increment to next match
                        else:
                            cur_tag = "O"
                    else:
                        cur_tag = "O"
                i_tags.append(cur_tag)
            yield f"{tok}\t" + "\t".join(i_tags) + "\n"

    #TODO: add unit test once
    def expanded_conll_from_token_sequences(self, extractor_names, tseqs, header=False) -> Iterable[str]:
        if header:
            yield "\t".join(["token"]+extractor_names) + "\n"
        for tseq in tseqs:
            yield from self.expanded_conll_from_token_sequence(extractor_names, tseq)
            yield "\n\n"

    def conll_from_token_sequences(self, extractor_names, tseqs):
        return "\n\n".join(self.conll_from_token_sequence(extractor_names, tseq) for tseq in tseqs)

    def extract(self, patname, text, first_only=False):
        toks = self.tokr.tokens(text)
        return self.extract_from_token_sequence(patname, toks, first_only)

    def dpaths_from_token_sequence(self, patname, toks):
        matches = self.scan(patname, toks)
        return [ (toks.find_paths(m.begin, m.end-1), self.normalized_extraction(toks, m)) 
                 for m in matches ]

    def dpaths_from_token_sequences(self, patname, toks):
        dpaths = []
        for seq in toks:
            dpaths += self.dpaths_from_token_sequence(patname, seq)
        return dpaths

    def tokens(self, text):
        toks = self.tokr.tokens(text)
        return [tok for tok in toks]

    def tokens_from_file(self,fname):
        text = self.file_contents(fname)
        return self.tokens(text)

    def present_in_file(self, patname, fname):
        text = self.file_contents(fname)
        return self.present(patname, text)

    def markup_file(self, patname, fname):
        text = self.file_contents(fname)
        return self.markup(patname, text)

    def extract_from_file(self, patname, fname, first_only=False):
        text = self.file_contents(fname)
        return self.extract(patname, text, first_only)

    # Or could use get_generic for this.
    def get_import(self, which):
        """"Returns sub-manager associated with name."""
        try:
            return self.imports[which]
        except KeyError:
            raise GenericException(msg="No such import '%s'" % which) from None

    def get_generic(self, which_dict, which_key, kind):
        try:
            return which_dict[which_key]
        except KeyError:
            # if which_dict is self.tests:
            #     extra = " (did you reference a phrase or parse expression with '&' instead of '@' by mistake?)"
            # elif which_dict is self.fas or which_dict is self.dep_fas:
            #     # extra = " (did you reference a token test expression with '@' instead of '&' by mistake?)"
            #     extra = " (did you reference a token test expression with '@' instead of '&' by mistake?)"
            # else:
            #     extra = ""
            extra = ""
            if hasattr(self, "pattern_file") and self.pattern_file is not None:
                raise GenericException(msg="No such %s '%s' in pattern file '%s'%s" % (kind, which_key, self.pattern_file, extra)) from None
            else:
                raise GenericException(msg="No such %s '%s'%s" % (kind, which_key, extra)) from None

    def get_test(self, patname):
        m = re.match(r'(\w+)\.(.*)', patname)
        if m:                               # Imported expression
            import_name = m.group(1)
            mgr = self.get_import(import_name)
            return mgr.get_test(m.group(2))
        else:
            return self.get_generic(self.tests, patname, "token test")

    def get_fa(self, patname):
        m = re.match(r'(\w+)\.(.*)', patname)
        if m:
            import_name = m.group(1)
            mgr = self.get_import(import_name)
            return mgr.get_fa(m.group(2))
        else:
            return self.get_generic(self.fas, patname, "phrase expression")

    def get_reversed_fa(self, patname):
        m = re.match(r'(\w+)\.(.*)', patname)
        if m:
            import_name = m.group(1)
            mgr = self.get_import(import_name)
            return mgr.get_reversed_fa(m.group(2))
        else:
            try:
                return self.ifas[patname]
            except KeyError:
                try:
                    fa = self.fas[patname]
                    print("Reversing", patname)
                    self.ifas[patname] = fa.reverse()
                    return self.ifas[patname]
                except KeyError:
                    return None

    def get_dep_fa(self, patname):
        m = re.match(r'(\w+)\.(.*)', patname)
        if m:
            import_name = m.group(1)
            mgr = self.get_import(import_name)
            return mgr.get_dep_fa(m.group(2))
        else:
            return self.get_generic(self.dep_fas, patname, "parse expression")

    def get_coord(self, patname):
        m = re.match(r'(\w+)\.(.*)', patname)
        if m:
            import_name = m.group(1)
            mgr = self.get_import(import_name)
            return mgr.get_coord(m.group(2))
        else:
            return self.get_generic(self.coords, patname, "coordinator expression")

    def get_test_expressions(self):
        return sorted(self.test_expressions.items(), key=lambda x: x[0])

    def get_fa_expressions(self):
        return sorted(self.fa_expressions.items(), key=lambda x: x[0])

    def get_coord_expressions(self):
        return sorted(self.coord_expressions.items(), key=lambda x: x[0])

    def defined_extractors(self):
        return set(k for dct in
                   (self.test_expressions, 
                    self.fa_expressions, 
                    self.dep_fa_expressions, 
                    self.coord_expressions)
                   for k in dct.keys())

    def extractor_is_defined(self, name):
        m = re.match(r'(\w+)\.(.*)', name)
        if m:
            import_name = m.group(1)
            mgr = self.imports[import_name]
            return mgr.extractor_is_defined(m.group(2))
        else:
            return name in self.tests or name in self.fas or name in self.dep_fas or name in self.coords

    def get_list_of_extractors(self):
        extractor_names = []
        for name in self.tests:
            extractor_names.append(name)
        for name in self.fas:
            extractor_names.append(name)
        for name in self.dep_fas:
            extractor_names.append(name)
        for name in self.coords:
            extractor_names.append(name)
        return extractor_names

    def seed(self, tseqs):
        for test in self.tests.values():
            for tseq in tseqs:
                test.seed(tseq)

    def requirements(self, name=None):
        """
        Return the set of external requirements (e.g., POS tagging) on which a given extractor (if name
        is specified) or the entire rule set depends.
        """

        if name is not None:
            ext, type_ = self.lookup_extractor(name)
            return ext.requirements()

        # Reliance on external resources currently arises entirely from the tests and dep expressions a rule set uses.
        # But note that we need to recurse into any imports.

        req = set()
        for test in self.tests.values():
            req |= test.requirements()

        for name, fa in list(self.dep_fas.items()):
            if isinstance(fa, Regex):
                fa = self.dep_fas[name] = fa.compile()
                fa.name = name
            req |= fa.requirements()

        for fam in self.imports.values():
            req |= fam.requirements()

        return req



