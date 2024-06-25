from collections import defaultdict, deque
from frozendict import frozendict
import itertools
import logging
import json
import os.path
import re
import sys
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Set, Tuple, Union

from nlpcore.dbfutil import GenericException, SimpleClass
from nlpcore.sentencer import Sentencer
from nlpcore.tokenizer import PlainTextTokenizer, TokenSequence

from .extractor import Extractor
from .fa import SequenceStartFiniteAutomaton, SequenceEndFiniteAutomaton, LexiconMatcher, ParseRootFiniteAutomaton
from .match import Match
from .regex import Regex
from .statement import \
    StatementParser, InterpretableRegion, \
    TestExpressionRegion, PhraseExpressionRegion, ParseExpressionRegion, \
    CoordRegion, FrameRegion, ImportRegion, MacroRegion
from .tokentest import AnyTokenTest, LearningTokenTest, MembershipTokenTest


"""
Provides the VRManager class, which can read a pattern file and build up
an interconnected set of FiniteAutomatons and other Extractor classes that
can recognize ocurrences of the language specified by the patterns.

The primary role of the VRManager is to hold an interrelated set of Extractors,
allowing them to cross-reference each other, and to to provide operations
for matching token sequences against the set of patterns.

Main operations are:
- parseFile - read pattern file, build Extractors
- match - match a pattern against token sequence at specified starting point
- search - match a pattern against token sequence at any starting point from specified one on
- matches - ...
- scan - match a pattern against token sequence, continuing...
"""


_logger = logging.getLogger(f"{__name__}.<module>")


# Maps pattern name to Extractor or similar instance implementing the pattern.
ExtrDict = Dict[str, Union[Extractor, Regex, 'VRManager']]

# Maps pattern name to RHS of pattern statement (expression string defining
# the pattern).
ExprDict = Dict[str, Optional[str]]


# Note that imports hold other VRManager instances representing patterns
# imported from external pattern files or from "namespaces" nested within
# a pattern file.
class VRManager(SimpleClass):
    # These ExtrDicts are mostly specialized to just one of
    # Extractor, Regex, VRManager, but not bothering to declare that way now.
    tests:   ExtrDict
    fas:     ExtrDict
    dep_fas: ExtrDict
    coords:  ExtrDict
    frames:  ExtrDict
    imports: ExtrDict
    test_expressions:   ExprDict
    fa_expressions:     ExprDict
    dep_fa_expressions: ExprDict
    coord_expressions:  ExprDict
    frame_expressions:  ExprDict
    import_expressions: ExprDict
    cached_tseq: Optional[TokenSequence]  # reset with each new tseq
    cache: Optional[Dict[Tuple, List]]  # ditto
    name: Optional[str]  # set if we are an import or namespace manager
    pattern_file: Optional[str]
    # Dict from pattern name to set of tseqs from current source doc
    # that have matched that named pattern. Used with WhenCoordinator.
    _recorded: Dict[str, Set[TokenSequence]]
    # There are other fields that we haven't bothered to declare yet.

    def __init__(self, *,
                 parent: 'VRManager' = None,
                 caching: bool = True,
                 exception_on_redefinition: bool = True,
                 verbose: bool = False,  # really verbose_imports
                 **kwargs):
        SimpleClass.__init__(self, **kwargs)
        self._default('name', None)
        self.parent = parent
        self.caching = caching
        self.exception_on_redefinition = exception_on_redefinition
        self.verbose = verbose
        self.tokr = PlainTextTokenizer(preserve_case=True)
        self._recorded = {}
        self.forget()

    @staticmethod
    def builtins() -> List[str]:
        """Names of all built-in patterns."""
        return ["ANY", "START", "END", "ROOT"]

    def __str__(self):
        return f"VRManager(name={self.name})"
        # return f"{object.__str__(self)}[name={getattr(self, 'name', None)}]"

    def forget(self, *names) -> None:
        """With no args, (re-)initialize ruleset to only the built-in rules.
        With args, remove the named rules."""
        if len(names) > 0:
            for name in names:
                _, type_, _ = self.lookup_extractor(name, fail_if_undef=False)
                if type_ is None:
                    continue
                elif type_ == 'test':
                    del self.tests[name]
                    del self.test_expressions[name]
                elif type_ == 'fa':
                    del self.fas[name]
                    del self.fa_expressions[name]
                elif type_ == 'dep_fa':
                    del self.dep_fas[name]
                    del self.dep_fa_expressions[name]
                elif type_ == 'coord':
                    del self.coords[name]
                    del self.coord_expressions[name]
                elif type_ == 'frame':
                    del self.frames[name]
                    del self.frame_expressions[name]
                self.clear_cache(name)
                self._recorded.pop(name, None)  # no exception if not present
            return

        self.clear_cache()
        self.clear_recorded()
        # self.imported_files = {}
        # START, END, ROOT, and ANY are our built-in rules.
        self.fas = {
            'START': SequenceStartFiniteAutomaton(),
            'END': SequenceEndFiniteAutomaton(),
            'ROOT': ParseRootFiniteAutomaton()
        }
        # So that lookup_own_pattern does not give an exception.
        self.fa_expressions = {
            'START': None,
            'END': None,
            'ROOT': None
        }
        self.fa_lexicon_imports = {}
        self.rfas = {}  # reversed FAs, not used, except in tests
        self.tests = {
            'ANY': AnyTokenTest()
        }
        self.test_expressions = {
            'ANY': None
        }
        self.imports = {}
        self.import_expressions = {}
        self.coords = {}
        self.coord_expressions = {}
        self.dep_fas = {}
        self.dep_fa_expressions = {}
        self.frames = {}
        self.frame_expressions = {}

    def clear_cache(self, name: Optional[str] = None) -> None:
        if name is not None and self.cache is not None:
            # Can't look up name directly, have to scan for it.
            for key in list(self.cache.keys()):
                if key[1] == name:
                    del self.cache[key]
            return

        self.cached_tseq = None
        if self.caching:
            self.cache = {}
        else:
            self.cache = None

    def set_name(self, name) -> None:
        self.name = name

    def set_embedding(self, embedding) -> None:
        self.embedding = embedding

    def read_embedding(self, embedding_file) -> None:
        from .extml import Embedding
        self.set_embedding(Embedding(embedding_file))

    def set_expander(self, expander) -> None:
        self.expander = expander

    def read_expander(self, term_expansion_directory) -> None:
        from nlpcore.term_expansion import TermExpansion
        expander = TermExpansion(input_directory=term_expansion_directory)
        expander.read_term_expansion_data()
        self.set_expander(expander)

    def model_path(self, model_name):
        """
        Return path for saving learned model.
        """
        mydir = os.path.dirname(self.pattern_file)
        return os.path.join(mydir, model_name)


    ###########################################################################
    # INGESTING RULES
    #

    def parse_file(self, fname):
        """Parse file with patterns, represent as internal set of Extractor's
        (or VRManager's for imports)."""
        # print(f"{self} parsing pattern file {fname}")
        self.pattern_file = fname
        block = self.file_contents(fname)
        self.parse_block(block)

    def parse_block(self, block):
        parser = StatementParser(block)
        statement: InterpretableRegion
        for statement in parser.statements():
            # print(f"{self} parsed region {statement}")
            try:
                statement.register(self)
            except Exception:
                import traceback
                traceback.print_exc()

    def register(self, region: InterpretableRegion):
        """Interpret a rule region (by calling region.interpret,
        which returns some kind of Extractor or similar object),
        and record the extractor in self."""

        # print(f"{self}.register called with {region}")

        # TODO: Implement
        if isinstance(region, MacroRegion):
            return

        # Get the dicts associated with the region type.
        extractors: ExtrDict
        expressions: ExprDict
        if isinstance(region, TestExpressionRegion):
            extractors, expressions = self.tests, self.test_expressions
        elif isinstance(region, PhraseExpressionRegion):
            extractors, expressions = self.fas, self.fa_expressions
        elif isinstance(region, ParseExpressionRegion):
            extractors, expressions = self.dep_fas, self.dep_fa_expressions
        elif isinstance(region, CoordRegion):
            extractors, expressions = self.coords, self.coord_expressions
        elif isinstance(region, FrameRegion):
            extractors, expressions = self.frames, self.frame_expressions
        elif isinstance(region, ImportRegion):
            extractors, expressions = self.imports, self.import_expressions
        else:
            raise TypeError("Unknown region type: %s" % region)

        name = region.spec()  # statement LHS str
        self.raise_if_defined(name)
        # Call interpret first so that if it throws, the expression map
        # does not get set either.
        extractors[name] = region.interpret(self)  # = Extractor instance (or VRManager for import)
        expressions[name] = region.expression()  # statement RHS str
        extractors[name].set_name(name)  # TODO? redundant with InterpretableRegion.interpret setting it

        return extractors[name]

    def raise_if_defined(self, name):
        """Raise exception if name is already used as a pattern name
        in this manager (unless this is disabled in the manager with
        exception_on_redefinition false, permitting redefinition)."""
        if not self.exception_on_redefinition:
            return
        delimiter, type_, expression = self.lookup_own_pattern(name)
        if delimiter is not None:
            raise GenericException(msg=f"'{name}' is already defined as a {type_} expression: {name} {delimiter} {expression}")

    ###########################################################################
    # Callbacks when ingesting rules
    #

    # This is currently an undocumented import type.
    # It has some advantages over the code in TokenTestExpression.atom();
    # see comments there.
    # TODO? There is a lot of duplication with that code in tokentest.py.
    def import_token_tests(self, name, expr) -> 'VRManager':
        # I presume 'i?' is here twice to allow either order "is" or "si".
        m = re.match('([cj]?){(.*)}(s?i?s?)$', expr)
        isfile = m.group(1)
        fname = m.group(2)
        insens = m.group(3) and 'i' in m.group(3)
        stemming = m.group(3) and 's' in m.group(3)
        subm = VRManager(verbose=self.verbose)
        # TODO Avoid duplicate messages from both here and resolve_import_path.
        # Here we also show the type; maybe not that important.

        if isfile:
            # Note that here "c" stands for (co)cluster, while in phrase
            # lexicons "c" stands for CSV.
            # This appears to create rules named by the cluster numbers,
            # the 0-based cluster indices.
            if isfile == 'c':
                labelfile, clusterfile = [self.resolve_import_path(x.strip())
                                          for x in fname.partition(";")
                                          if x != ";"]
                with open(labelfile) as infile:
                    labels = dict(enumerate([x.strip() for x in infile]))
                memberships = defaultdict(set)
                if self.verbose:
                    print("VR: Importing cluster file %s" % clusterfile)
                with open(clusterfile) as infile:
                    for number, line in enumerate(infile):
                        cluster = line.strip()
                        memberships[cluster].add(labels[number])
                for cluster, members in memberships.items():
                    subm.tests[cluster] = MembershipTokenTest(members=members,
                        case_insensitive=insens, stemming=stemming, name=cluster)

            # The "j" JSON stuff here appears to have essentially the same form
            # as the coclustering stuff, using the fact that JSON can express
            # dicts and sets (sets as lists).
            # But I imagine who/whatever creates the json files takes the
            # opportunity to use more meaningful rule names (vs 0-based idxs).
            elif isfile == 'j':
                if self.verbose:
                    print("VR: Importing json file %s" % fname)
                with open(fname) as infile:
                    membmaps = json.load(infile)
                for cluster, members in membmaps.items():
                    subm.tests[cluster] = MembershipTokenTest(members=members,
                        case_insensitive=insens, stemming=stemming, name=cluster)

        else:
            path = self.resolve_import_path(fname)
            if self.verbose:
                print("VR: Importing token list file %s" % path)
            with open(path) as infile:
                members = [x.strip() for x in infile]
            subm.tests[name] = MembershipTokenTest(members=members,
                case_insensitive=insens, stemming=stemming, name=name)

        return subm

    def import_file(self, fname=None) -> 'VRManager':
        """
        Process statements in the indicated file and return a new VRManager
        populated with the rules it contains.
        If fname is None, return new empty VRManager (used for local name
        spaces, not unlike a "here document" in bash).
        """
        # This kind of caching can lead to confusing results,
        # since Valet expressions can import from data files.
        # If the expressions that import those files don't change,
        # but the data files do, behavior will be incorrect.
        # mtime = os.path.getmtime(path)
        # try:
        #     subm, imported_mtime = self.imported_files[path]
        #     if mtime <= imported_mtime:
        #         return subm
        # except KeyError:
        #     pass
        subm = VRManager(verbose=self.verbose)
        if fname is None:  # "namespace import"
            subm.parent = self
        else:
            path = self.resolve_import_path(fname)
            subm.parse_file(path)
            # We didn't use to do this for this kind of import,
            # but we need it to make the substitution mechanism work
            # when doing substitutions in imported rules.
            # It does open up the possibility of an imported rules file
            # accidentally (or even deliberately) referencing a parent
            # rule, though.
            # Imports have made rule referencing tricky, as seen
            # especially in match.query_name_matches and test_frame.py.
            subm.parent = self
        # self.imported_files[path] = (subm, mtime)
        return subm

    def import_lexicon_matcher(self, fname, case_insensitive, is_csv, target_column) -> LexiconMatcher:
        """Returns a LexiconMatcher, a FiniteAutomaton subclass supporting
        literal phrase expressions."""
        path = self.resolve_import_path(fname)
        return LexiconMatcher(path, case_insensitive, is_csv, target_column, self)

    def resolve_import_path(self, fname):
        """
        Return resolved path to specified rules file.
        Throws exception if unable to resolve to an existing file.
        """
        path = None
        resolution = None  # for error messages
        if os.path.abspath(fname) == fname:  # Absolute path
            path = fname
            resolution = "absolute"
        elif os.path.exists(fname):  # Resolvable from cwd
            path = os.path.abspath(fname)
            resolution = "cwd"
        else:
            # Relative to directory containing current pattern file
            # import pkg_resources
            cur_path = None
            if hasattr(self, 'pattern_file'):
                mydir = os.path.dirname(self.pattern_file)
                cur_path = os.path.join(mydir, fname)
            if cur_path is not None and os.path.exists(cur_path):
                path = cur_path
                resolution = "parent"
            # The vrules file is one of the built-ins.
            # elif pkg_resources.resource_exists(__name__, "data/%s" % fname):
            #     path = pkg_resources.resource_filename(__name__, "data/%s" % fname)
            else:
                # https://stackoverflow.com/questions/58520128/how-to-use-importlib-resources-pathpackage-resource
                # In later versions of python there are other APIs that may be easier.
                from importlib import resources
                try:
                    # We'd need to add an __init__.py to the valetrules/data dir for this to work.
                    # with importlib.resources.path("valetrules.data", fname) as p:
                    #     path = p
                    # This works without that.
                    with resources.path("valetrules", "manager.py") as p:
                        cur_path = p.parent / "data" / fname
                        if os.path.exists(cur_path):
                            path = cur_path
                            resolution = "builtin"
                except Exception:
                    # import traceback
                    # traceback.print_exc()
                    pass
        if path is None or not os.path.exists(path):
            msg = "Can't resolve import path '%s' (resolution='%s', path='%s')" % (fname, resolution, path)
            raise GenericException(msg=msg)
        elif self.verbose:
            print("Resolved import path '%s' (resolution='%s', path='%s')" % (fname, resolution, path))
        return path


    ###########################################################################
    # INTROSPECTING RULES
    #

    imported_rule_re = re.compile(r'(\w+)\.(.*)')  # pre-compile

    def parse_import_name(self, name):
        """For imported rule name, return initial import name and remainder
        (w/o dot); otherwise return None and None.
        E.g., for import1.import2.rule, return import1 and import2.rule"""
        m = self.imported_rule_re.match(name)
        if m:
            return m.group(1), m.group(2)
        return None, None

    # Or could use get_generic for this.
    def get_import(self, name) -> 'VRManager':
        """Returns sub-manager associated with import name, if any.
        Does not recurse into imports.
        Does not recurse into parent manager if not found in this one.
        Raises exception if not found."""
        try:
            return self.imports[name]
        except KeyError:
            raise GenericException(msg="No such import '%s'" % name) from None

    #
    # Most of what's below in this section is obsolete or at least incomplete
    # because it doesn't handle either lookup in parent manager
    # or substititions.
    # There MIGHT be cases where it's useful, but typically callers
    # should use something like lookup_extractor instead of these methods.
    #

    # A generic version of a portion of the getter logic, the part that
    # looks only in the current manager (self).
    # def get_generic(self, which_dict, which_key, kind) -> Union[Extractor, Regex, 'VRManager']:
    #     """Does not recurse into imports for keys that are qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     try:
    #         return which_dict[which_key]
    #     except KeyError:
    #         if hasattr(self, "pattern_file") and self.pattern_file is not None:
    #             raise GenericException(msg="No such %s '%s' in pattern file '%s'" % (kind, which_key, self.pattern_file)) from None
    #         else:
    #             raise GenericException(msg="No such %s '%s'" % (kind, which_key)) from None

    # def get_test(self, patname, substitutions=None) -> TokenTest:
    #     """Recurses into imports for qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     import_name, remainder = self.parse_import_name(patname)
    #     if import_name is not None:
    #         mgr = self.get_import(import_name)
    #         return mgr.get_test(remainder)  # recurse
    #     else:
    #         return cast(TokenTest, self.get_generic(self.tests, patname, "token test"))

    # def get_fa(self, patname) -> FiniteAutomaton:
    #     """Recurses into imports for qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     import_name, remainder = self.parse_import_name(patname)
    #     if import_name is not None:
    #         mgr = self.get_import(import_name)
    #         return mgr.get_fa(remainder)  # recurse
    #     else:
    #         return cast(FiniteAutomaton, self.get_generic(self.fas, patname, "phrase expression"))

    # The reversed FA concept is not active anymore, but we now have tests
    # for it that call this. Dayne told me that at one point he tried rfas
    # for searching backward in the Prefix coordinator.
    def get_reversed_fa(self, patname):
        """Recurses into imports for qualified names.
        Does not recurse into parent manager.
        Raises exception if not found."""
        import_name, remainder = self.parse_import_name(patname)
        if import_name is not None:
            mgr = self.get_import(import_name)
            return mgr.get_reversed_fa(remainder)  # recurse
        else:
            try:
                return self.rfas[patname]
            except KeyError:
                fa = self.fas[patname]
                if isinstance(fa, Regex):
                    fa = self.fas[patname] = self.compile_regex_to_fa(patname, fa)
                # print("Reversing", patname)
                rfa = self.rfas[patname] = fa.reverse()
                return rfa

    # def get_dep_fa(self, patname):
    #     """Recurses into imports for qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     import_name, remainder = self.parse_import_name(patname)
    #     if import_name is not None:
    #         mgr = self.get_import(import_name)
    #         return mgr.get_dep_fa(remainder)  # recurse
    #     else:
    #         return self.get_generic(self.dep_fas, patname, "parse expression")

    # def get_coord(self, patname):
    #     """Recurses into imports for qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     import_name, remainder = self.parse_import_name(patname)
    #     if import_name is not None:
    #         mgr = self.get_import(import_name)
    #         return mgr.get_coord(remainder)  # recurse
    #     else:
    #         return self.get_generic(self.coords, patname, "coordinator expression")

    # def get_frame(self, patname):
    #     """Recurses into imports for qualified names.
    #     Does not recurse into parent manager.
    #     Raises exception if not found."""
    #     import_name, remainder = self.parse_import_name(patname)
    #     if import_name is not None:
    #         mgr = self.get_import(import_name)
    #         return mgr.get_frame(remainder)  # recurse
    #     else:
    #         return self.get_generic(self.frames, patname, "frame expression")

    ###########################################################################

    def all_extractor_names(self) -> List[str]:
        return list(name for dct in
                    (self.test_expressions,
                     self.fa_expressions,
                     self.dep_fa_expressions,
                     self.coord_expressions,
                     self.frame_expressions)
                    for name in dct.keys())

    def get_test_expressions(self):
        """Tuples of name and expression strings, sorted by name."""
        return sorted(self.test_expressions.items(), key=lambda item: item[0])

    def get_fa_expressions(self):
        """Tuples of name and expression strings, sorted by name."""
        return sorted(self.fa_expressions.items(), key=lambda item: item[0])

    def get_dep_fa_expressions(self):
        """Tuples of name and expression strings, sorted by name."""
        return sorted(self.dep_fa_expressions.items(), key=lambda item: item[0])

    def get_coord_expressions(self):
        """Tuples of name and expression strings, sorted by name."""
        return sorted(self.coord_expressions.items(), key=lambda item: item[0])

    def get_frame_expressions(self):
        """Tuples of name and expression strings, sorted by name."""
        return sorted(self.frame_expressions.items(), key=lambda item: item[0])

    ###########################################################################

    # For making nice error messages.
    extractor_type_to_long_name_map = {
        'test':   'token test',
        'fa':     'phrase',
        'dep_fa': 'parse',
        'coord':  'coordinator',
        'frame':  'frame'
    }

    # Started as a staticmethod, but caller can't import this module
    # due to circular reference.
    def extractor_type_to_long_name(self, type_):
        return VRManager.extractor_type_to_long_name_map[type_]


    ###########################################################################


    # One may wonder why we need both lookup_extractor and lookup_pattern.
    # One reason may be that we may use lookup_pattern during rule parsing,
    # when we may have patterns/expressions but not yet extractors?
    # Also, it may not matter, but looking up an extractor can have
    # the side effect of compiling Regex's into FAs (in lookup_own_extractor).
    # So there might be good reasons.
    # TODO? OTOH, it also seems not implausible that we might be able
    # to combine them.
    # FWIW, lookup_extractor is used much more; in fact lookup_pattern
    # is only called by test_is_defined, and a few legacy scripts
    # that need updating.


    def lookup_own_pattern(self, name):
        """Return tuple with pattern definition delimiter (~, ->, ^, $, :),
        (quasi-)type name (test, fa, dep_fa, coord, frame),
        and expression body; or tuple with Nones if not found.
        Expression body is None for built-ins."""
        if name in self.tests:
            return '#', 'test', self.test_expressions[name]
        elif name in self.fas:
            return '->', 'fa', self.fa_expressions[name]
        elif name in self.dep_fas:
            return '^', 'dep_fa', self.dep_fa_expressions[name]
        elif name in self.coords:
            return '~', 'coord', self.coord_expressions[name]
        elif name in self.frames:
            return '$', 'frame', self.frame_expressions[name]
        else:
            return None, None, None

    # This is virtually identical to lookup_extractor,
    # except that it doesn't pay attention to substitutions,
    # and it doesn't (in _own_) compile Regex's into FA's.
    def lookup_pattern(self, name, fail_if_undef=True):
        """Return tuple with pattern definition delimiter str (~, ->, ^, $, :),
        (quasi-)type name str (test, fa, dep_fa, coord, frame), and expression
        body str, or tuple of Nones if not found and fail_if_undef=False.
        Expression body is None for built-ins."""
        import_name, remainder = self.parse_import_name(name)
        if import_name is not None:
            if import_name in self.imports:
                mgr = self.imports[import_name]
                ext, type_, subst = mgr.lookup_pattern(remainder, fail_if_undef=False)
                if ext is not None:
                    return ext, type_, subst
                elif self.parent is not None:
                    return self.parent.lookup_pattern(name, fail_if_undef=fail_if_undef)
                elif not fail_if_undef:
                    return None, None, None
                else:
                    raise GenericException(msg="Pattern name not found: %s" % name)
            # else fall through, and lookup in parent manager below

        delimiter, type_, expression = self.lookup_own_pattern(name)
        if delimiter is not None:
            return delimiter, type_, expression
        elif self.parent is not None:
            return self.parent.lookup_pattern(name, fail_if_undef=fail_if_undef)
        elif not fail_if_undef:
            return None, None, None
        else:
            raise GenericException(msg="Pattern name not found: %s" % name)

    @staticmethod
    def merge_substitutions(ext, substitutions: Optional[Mapping[str, str]]):
        """Merge substitution mappings from extractor and argument,
        favoring extractor in case of duplicate keys (to enable override).
        Does not actually make any substitutions."""
        if not hasattr(ext, 'substitutions') or ext.substitutions is None:
            return substitutions
        if substitutions is None:
            return ext.substitutions
        # _logger.info(f"Merging extractor {ext} substitutions {ext.substitutions} with incoming substitutions {substitutions}")
        return {**ext.substitutions, **substitutions}

    # Note that in the presence of substitutions, any pattern name
    # mention in a rule definition becomes a sort of formal parameter,
    # whose actual argument is provided by a substitution.
    # (That seems to be why macro definitions were never completed
    # in statement.py, as substutitions can handle a lot of the
    # desired applications.)
    @staticmethod
    def apply_substitutions(patname: str, substitutions: Optional[Mapping[str, str]]) -> str:
        """Make any substitutions specified for patname, repeating
        for each substituted patname, returning final patname."""
        # orig_patname = patname
        while substitutions is not None and patname in substitutions:
            patname = substitutions[patname]
        # if patname != orig_patname:
        #     # It would be nice to also print that this was done per the
        #     # substitutions for which rule, but we don't have that info.
        #     _logger.info(f"{orig_patname} -> {patname}")
        return patname

    # One key thing done by this method is to take the Regex instances
    # stored at rule parse time into the fa and dep_fa tables and
    # COMPILE THEM into {,Arc}FiniteAutomata, replacing them in the tables.
    #
    # This compilation was previously done at parse time in the Region
    # _interpret method, but was moved to here in the change that allowed
    # @ and & to be used interchangably, Feb 14 2022 3:25 PM.
    #
    # This delay allows all rules to be defined before an fa is compiled,
    # enabling it to be compiled with knowledge of whether a rule reference
    # refers to a token test or to a callout FA, which knowledge can be
    # used to make the compiled FA (slightly?) more efficient.
    # That information was previously conveyed by the & vs @ symbol.
    def lookup_own_extractor(self, name: str):
        """Return tuple with extractor object and (quasi-)type name
        (test, fa, dep_fa, coord, frame), or tuple of Nones if not found."""
        if name in self.coords:
            ext = self.coords[name]
            return ext, 'coord'
        elif name in self.fas:
            fa = self.fas[name]
            if isinstance(fa, Regex):
                fa = self.fas[name] = self.compile_regex_to_fa(name, fa)
            return fa, 'fa'
        elif name in self.dep_fas:
            fa = self.dep_fas[name]
            if isinstance(fa, Regex):
                fa = self.dep_fas[name] = self.compile_regex_to_fa(name, fa)
            return fa, 'dep_fa'
        elif name in self.frames:
            ext = self.frames[name]
            return ext, 'frame'
        elif name in self.tests:
            ext = self.tests[name]
            return ext, 'test'
        else:
            return None, None

    def compile_regex_to_fa(self, patname, regex: Regex) -> 'FiniteAutomaton':
        """Also set fa.name."""
        fa = regex.compile()
        # fa.dump()  # debug
        fa.name = patname
        return fa

    # The lookup process is about resolving names to extractors.
    # This involves several things that are interwined here:
    # - resolving QUALIFIED (dotted) names in CHILD file and namespace import managers
    # - resolving names in PARENT managers if not found in current mangager
    # - substituting names as specified in name BINDINGS in rule definitions
    def lookup_extractor(self, name, substitutions=None, fail_if_undef=True):
        """Return tuple with extractor object, (quasi-)type name
        (coord, fa, dep_fa, frame, test), and merged substitutions,
        or tuple of Nones if not found and fail_if_undef=False."""
        import_name, remainder = self.parse_import_name(name)
        if import_name is not None:
            if import_name in self.imports:
                mgr = self.imports[import_name]
                # False here because we want to say "a.b not found" below,
                # not have this say "b not found" here if this could throw.
                ext, type_, subst = mgr.lookup_extractor(remainder, substitutions=substitutions, fail_if_undef=False)
                if ext is not None:
                    return ext, type_, subst
                elif self.parent is not None:
                    return self.parent.lookup_extractor(name, substitutions=substitutions, fail_if_undef=fail_if_undef)
                elif not fail_if_undef:
                    return None, None, None
                else:
                    raise GenericException(msg="Pattern name not found: %s" % name)
            # else fall through, and look up in parent manager below

        # Note FWIW this could be a dotted name from above, which won't
        # be found as "own", but the logic seems OK and is nicely parallel
        # to that above.
        ext, type_ = self.lookup_own_extractor(name)
        if ext is not None:
            # Here is where we merge substitutions.
            subst = self.merge_substitutions(ext, substitutions)
            return ext, type_, subst
        elif self.parent is not None:
            return self.parent.lookup_extractor(name, substitutions=substitutions, fail_if_undef=fail_if_undef)
        elif not fail_if_undef:
            return None, None, None
        else:
            raise GenericException(msg="Pattern name not found: %s" % name)

    def substitute_and_lookup(self, patname, substitutions):
        """Convenience method calling apply_substitutions and then
        lookup_extractor, returning substituted name, extractor object,
        (quasi-)type name, and merged substitutions."""
        patname = self.apply_substitutions(patname, substitutions)
        ext, type_, merged_substitutions = self.lookup_extractor(patname, substitutions=substitutions)
        return patname, ext, type_, merged_substitutions

    def lookup_learning_test(self, name):
        """Returns None if not found."""
        extractor, type_, _ = self.lookup_extractor(name, fail_if_undef=False)
        if extractor is None:
            return None
        if type_ != 'test':
            return None
        if not isinstance(extractor, LearningTokenTest):
            return None
        return extractor

    # Called when compiling FAs.
    def test_is_defined(self, name):
        """True if defined either in self or ancestors."""
        _, type_, _ = self.lookup_pattern(name, fail_if_undef=False)  # all None's if not defined
        return type_ == "test"

    # Originally called on anchor name from frame rule parsing code and
    # on pattern name from select coordinator code, but both calls are now
    # commented out.
    def extractor_is_defined(self, name):
        """True if defined either in self or ancestors."""

        _, type_, _ = self.lookup_pattern(name, fail_if_undef=False)  # all None's if not defined
        return type_ is not None

    ###########################################################################

    def seed(self, tseqs):
        for test in self.tests.values():
            for tseq in tseqs:
                test.seed(tseq)

    def requirements(self, name=None, substitutions=None):
        """
        Return the set of external requirements (e.g., POS tagging) on which
        a given extractor (if name is specified) or the entire rule set depends.
        """

        if name is not None:
            _, ext, _, merged_substitutions = self.substitute_and_lookup(name, substitutions)
            return ext.requirements(merged_substitutions)

        # Reliance on external resources currently arises entirely
        # from the token tests and dep expressions a rule set uses.
        # But note that we need to recurse into any imports.

        req = set()
        for test in self.tests.values():
            req |= test.requirements(substitutions)

        for name, fa in list(self.dep_fas.items()):
            if isinstance(fa, Regex):
                # See comments at lookup_own_extractor.
                fa = self.dep_fas[name] = self.compile_regex_to_fa(name, fa)
            req |= fa.requirements(substitutions)

        for vrm in self.imports.values():
            req |= vrm.requirements(substitutions)  # recurse

        return req


    ###########################################################################
    # RUNNING RULES
    #

    # Note that caching currently only happens for matches generated by
    # Manager's _scan() and _matches() methods, whereas, e.g., tokentest
    # matches generated by FAs don't get cached.
    # However, all of the main Manager methods scan(), search(), matches(),
    # and match are routed through _scan() or _matches(), and many Extractor
    # methods are routed BACK through Manager's scan() or matches(), including
    # FA callouts to non-tokentests and coordinator calls to named patterns,
    # so most generated matches do get cached.
    #
    # Note also that matches of a pattern are cached in the manager that the
    # pattern is REFERENCED in (and similarly for "recording" matching patterns
    # as done for WhenCoordinator).
    # That's because when dealing with another pattern referenced by name,
    # extractors are generally calling self.manager.method()for methods like
    # scan() or record().
    # FWIW, that means that if the same pattern is referenced from two different
    # managers, cached matches in one manager would not be found when looked up
    # from another manager.
    #
    # TODO Should this take a self arg? I see a warning that suggests it should.
    def caching(func):  # func is the wrapped method or function, eg scan or matches
        """
        Used as a decorator to wrap key methods with caching of matches
        returned from running rules, to avoid repeating work unnecessarily.
        Caches values for only a single tseq at a time.
        """
        def wrapper(self, name, ext, type_, toks, start=0, end=None, substitutions=None):
            if self.cache is not None:
                if toks is not self.cached_tseq:
                    self.cache = {}
                    self.cached_tseq = toks
                if substitutions is not None:
                    substitutions = frozendict(substitutions)
                key = (func, name, type_, start, end, substitutions)
                # print(f"Mgr[{self.name}] checking cache for {(func.__name__, *key[1:])}")
                if (hit := self.cache.get(key)) is None:
                    hit = list(func(self, name, ext, type_, toks, start=start, end=end, substitutions=substitutions))
                    self.cache[key] = hit
                # else:
                #     print(f"Using cached value {hit} for '{key}' for {toks} {toks.tokens}")
                for m in hit:
                    yield m
            else:
                for m in func(self, name, ext, type_, toks, start=start, end=end, substitutions=substitutions):
                    yield m
        return wrapper

    @caching
    def _scan(self, name, ext, type_, toks, start=0, end=None, substitutions=None) -> Iterator[Match]:
        """
        Generate a sequence of *all* matches in the token sequence
        within the indicated start/end range.
        """

        # _logger.info(f"In VRManager._scan for {name} {ext}")

        # not currently a generator when type_ == 'frame', FWIW
        gen = ext.scan(toks, start, end, substitutions=substitutions)
        for m in gen:
            if m.begin < start or (end is not None and m.end > end):
                # Probably shouldn't happen now, so leave this in
                # for a while and see if it ever does.
                # If not, perhaps change to raise an exception.
                print(f"Returned match begin/end ({m.begin},{m.end}) from VRM._scan exceeds specified limits <{start},{end}> for '{type_}' extractor '{name}'")
                # raise GenericException(msg=f"Returned match begin/end <{m.begin},{m.end}> from VRM._scan exceeds specified limits ,{start},{end}> for '{type_}' extractor '{name}'")
                continue

            # Note FWIW this is one key place where match names are assigned.
            # The other one in this class is _matches.
            #
            # Matches of internal subexpressions don't get to here and so
            # don't get named here (thus have no name attr, or name is None,
            # unless already named elsewhere).
            #
            # FAs name matches after themselves.
            # It seems like coordinators try to name matches after themselves
            # when they create them, but usually they don't HAVE names
            # themselves (or name is None), although I've seen exceptions.
            #
            # Names can sometimes get OVERWRITTEN here.
            # The only time I've seen that happen is when imports are involved
            # so that the outer manager knows the extractor
            # as import_name.rule_name, but the inner manager knows it only
            # as rule_name.
            # if m.name is not None and m.name != name:
            #     print(f"Renaming match from {m.name} to {name}: {m}")
            m.name = name
            yield m
            # _logger.info(f"Resuming VRManager._scan for {name} {ext}")

        # _logger.info(f"Leaving VRManager._scan for {name} {ext}")
        # return  # place to set breakpoint

    # This seems not to be called.
    def match(self, patname, toks, start=0, end=None, substitutions=None) -> Optional[Match]:
        """
        Return the *longest* match encountered starting (only) at the
        start token, within the indicated start/end range, or None if none.
        """
        patname, ext, type_, merged_substitutions = self.substitute_and_lookup(patname, substitutions=substitutions)
        match = None
        for m in self._scan(patname, ext, type_, toks, start, end, merged_substitutions):
            if m.begin != start:
                return match
            if match is None or m.end > match.end:
                match = m
        return match

    # This is used for "callouts" in FA and ArcFA,
    # and also by ConnectsCoordinator.
    def matches(self, patname, toks, start=0, end=None, substitutions=None) -> Iterator[Match]:
        """
        Looks up an extractor for 'patname' and delegates to that extractor's
        matches() method, optionally doing cache lookup.
        """
        patname, ext, type_, merged_substitutions = self.substitute_and_lookup(patname, substitutions=substitutions)
        for m in self._matches(patname, ext, type_, toks, start, end, merged_substitutions):
            yield m

    @caching
    def _matches(self, name, ext: Extractor, type_, toks, start=0, end=None, substitutions=None) -> Iterator[Match]:
        """
        Generate a sequence of *all* matches in the token sequence starting at
        the specific start value, ending no later than the specified end.
        """
        for m in ext.matches(toks, start, end, substitutions=substitutions):
            # TODO Should this be != start?
            if m.begin < start or (end is not None and m.end > end):
                # Probably shouldn't happen now, so leave this in
                # for a while and see if it ever does.
                # If not, perhaps change to raise an exception.
                print(f"Returned match begin/end ({m.begin},{m.end}) from VRM._matches exceeds specified limits <{start},{end}> for '{type_}' extractor '{name}'")
                # raise GenericException(msg=f"Returned match begin/end <{m.begin},{m.end}> from VRM._matches exceeds specified limits ,{start},{end}> for '{type_}' extractor '{name}'")
                continue

            # Note FWIW this is one key place where match names are assigned.
            # The other one in this class is _scan; see comments there.
            m.name = name
            yield m

    # May not need to handle substitutions, since it doesn't get called
    # recursively like scan does.
    def search(self, patname, toks, start=0, end=None) -> Optional[Match]:
        """
        Return the *first* match encountered
        within the indicated start/end range, or None if none.
        """
        ext, type_, _ = self.lookup_extractor(patname)
        for m in self._scan(patname, ext, type_, toks, start, end):
            return m
        return None

    # Be aware that the method names scan/search/match/matches are widely used
    # across classes including VRManager and the various extractor classes
    # like TokenTest, {Arc,}FiniteAutomaton, Coordinator, and Frame,
    # but often with subtle differences in their semantics.
    #
    # We rarely or never pass in substitutions from the outside when calling
    # methods like scan(), but when scan() gets called recursively as one
    # rule references another, rules can have associated substitutions,
    # and those need to passed down the call tree and applied.
    # For example, in the code below, patname may have associated
    # substitutions specified by its rule definition.
    # See tests/test_binding.py for examples.
    def scan(self, patname, toks, start=0, end=None, substitutions=None) -> Iterator[Match]:
        """
        Generate a sequence of *all* matches in the token sequence
        within the indicated start/end range.
        """
        patname, ext, type_, merged_substitutions = self.substitute_and_lookup(patname, substitutions=substitutions)
        for m in self._scan(patname, ext, type_, toks, start, end, merged_substitutions):
            yield m

    ###########################################################################

    # This is new code to support the WhenCoordinator, which for the first
    # time involves the Manager tracking information across different
    # token sequences within a document.
    #
    # Here the passed-in tseq should be the same as the self.current_tseq,
    # but I kind of like passing it in anyway, partly because I'd like to see
    # the manager be more re-entrant. TBD.

    def record(self, patname: str, tseq: TokenSequence) -> None:
        """Record that there was a match of the given pattern
        in the given tseq."""
        # print(f"Mgr[{self.name}] recording match of {patname} for {tseq.tokens}")
        if patname not in self._recorded:
            self._recorded[patname] = {tseq}
        else:
            self._recorded[patname].add(tseq)

    def recorded(self, patname: str, tseq: TokenSequence) -> bool:
        """Query whether there was a match of the given pattern
        in a tseq OTHER THAN the given tseq."""
        # print(f"Mgr[{self.name}] checking for recorded match of {patname} during {tseq.tokens}")
        if patname not in self._recorded:
            return False
        tseqs = self._recorded[patname]
        if tseq in tseqs:
            # This would be an unusual case where WhenCoordinator.scan
            # recurses back into itself so that a rule is recorded as
            # matching the current tseq before another reference to
            # that rule has been evaluated (recorded checked).
            return len(tseqs) > 1
        else:
            return len(tseqs) > 0

    # This should be called when the end of a "document" is reached,
    # or (probably slightly better) before a new one is started.
    def clear_recorded(self) -> None:
        self._recorded.clear()

    ###########################################################################
    # MARKUP UTILITIES
    #

    # These are a pretty haphazard set of utility methods.
    # At least some of the methods are pretty obsolete, and most are not
    # well maintained, nor are any currently covered by tests.

    def markup_from_token_sequences(self, patname, tseqs, trim=False):
        """Scan the pattern on the tseqs.
        Return string with the source text, modified by marking
        matches of the pattern in the text.
        The tseqs should be from the same source and in source order.
        Matches overlapping previous matches are dropped.
        Trim true means return only those source text lines with markup."""
        matches = []
        submatches = []
        for tseq in tseqs:
            lastm = None
            m: Match
            for m in sorted(list(self.scan(patname, tseq))):
                if lastm is None or not lastm.overlaps(m):
                    matches.append(m)
                    # TODO There are a lot of different submatch attributes;
                    # why do we specially care about this one?
                    if hasattr(m, "submatch"):
                        matches.append(m.submatch)
                        submatches.append(m.submatch)
                elif lastm is not None:
                    print(f"Dropping match {m} due to overlap", file=sys.stderr)
                lastm = m
        text = tseqs[0].text  # assuming same for all tseqs
        return self.markup_sorted_nonoverlapping_matches(matches, submatches, text, trim)

    # The markup scheme does not have a good way of marking overlapping matches;
    # it would be complicated to implement and hard to interpret the markup.
    def markup_sorted_nonoverlapping_matches(self, matches, submatches, text, trim=False):
        """Auxiliary to other markup methods.
        Passed "matches" present in the passed "submatches" are marked differently,
        with curly braces instead of triangle brackets."""
        # The idea above is probably to be able to mark both matches and their
        # presumed most important submatches, but I'm skeptical that this
        # would work very well except in certain cases, and where the match
        # and submatch either coincide or don't overlap at all
        # (can the latter happen?).
        # Probably those cases would be filter family and related coordinators
        # where the submatch has the same extent as the match.
        # Also, since the second coinciding match would be dropped,
        # and in the callers the match is added before the submatch,
        # it seems we wouldn't see the submatch markup.
        # And in fact so far I haven't seen any.
        for m in reversed(list(matches)):
            start = m.start_offset(absolute=True)
            end = m.end_offset(absolute=True)
            if m not in submatches:
                text = text[0:start] + ' >>> ' + text[start:end] + ' <<< ' + text[end:]
            else:
                text = text[0:start] + ' {{{ ' + text[start:end] + ' }}} ' + text[end:]
        if trim:
            matchers = [line for line in re.split('\n', text) if re.search(r'>>>|<<<|{{{|}}}', line)]
            text = '\n'.join(matchers)
        return text

    # TODO? This repeats too much code from markup_from_token_sequences;
    # they should probably both be refactored to avoid that.
    def markup_from_matches(self, matches, text, trim=False):
        """Like markup_from_token_sequences, but takes as input
        matches already generated and the source text.
        The matches should be from the same source."""
        # TokenSequence does not have its own __eq/hash__ methods,
        # so there's no real reason to work with the id's, unless
        # we think that might change.
        matches_by_tseq_id = defaultdict(list)
        tseqs_by_id = {}
        for m in matches:
            matches_by_tseq_id[id(m.seq)].append(m)
            tseqs_by_id[id(m.seq)] = m.seq
        sorted_tseq_ids = sorted(matches_by_tseq_id.keys(), key=lambda id_: tseqs_by_id[id_].offset)
        matches_ = []
        submatches_ = []
        for id_ in sorted_tseq_ids:
            # tseq = tseqs_by_id[id_]
            lastm = None
            m: Match
            for m in sorted(matches_by_tseq_id[id_]):
                if lastm is None or not lastm.overlaps(m):
                    matches_.append(m)
                    # TODO There are a lot of different submatch attributes;
                    # why do we specially care about this one?
                    if hasattr(m, "submatch"):
                        matches_.append(m.submatch)
                        submatches_.append(m.submatch)
                elif lastm is not None:
                    print(f"Dropping match {m} due to overlap", file=sys.stderr)
                lastm = m
        return self.markup_sorted_nonoverlapping_matches(matches_, submatches_, text, trim)

    def markup_from_token_sequence(self, patname, tseq, trim=False):
        return self.markup_from_token_sequences(patname, [tseq], trim)

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

    # TODO 'toks' is not used.
    def normalized_extraction(self, toks, match):
        fragment = match.matching_text()
        fragment = re.sub(r'\s+', ' ', fragment)
        return fragment  # + "\n\t" + str(toks)
        # return str(match) + ":" + fragment

    # "Frame" in the next several methods below has a different meaning
    # from its now-primary meaning as in frame.py and match.py.Frame.
    # Below, frame seems to denote an edge path between the start and end
    # of a match.

    # There is a new get_frame method consistent with the now-primary
    # meaning of "frame".
    def get_frame_old(self, toks, match):
        return toks.find_paths(match.begin, match.end)

    def frame_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.get_path(toks, m)
            else:
                return None
        else:
            matches = self.scan(patname, toks)
            return [str((self.normalized_extraction(toks, m), self.get_path(toks, m))) for m in matches]

    def frame_from_token_sequences(self, patname, toks, first_only=False):
        paths = []
        for seq in toks:
            paths += self.path_from_token_sequence(patname, seq,first_only)
        return paths

    # There's a bit of confusion in the naming here regarding single
    # vs multiple paths. See comment at find_paths.
    def get_path(self, toks, match):
        # return toks.find_paths(match.begin,match.end)
        # Note:  find paths uses inclusive end, match uses exclusive end
        return toks.find_paths(match.begin, match.end-1)

    # TODO This looks odd; it doesn't use 'match'.
    def get_pos(self, toks, match):
        return [(tok,pos) for (tok,pos) in zip(toks, toks.annotations["pos"])]

    def pos_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.get_pos(toks, m)
            else:
                return None
        else:
            matches = self.scan(patname, toks)
            return [str((self.normalized_extraction(toks, m), self.get_pos(toks, m))) for m in matches]

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
            matches = self.scan(patname, toks)
            return [str((self.normalized_extraction(toks, m), self.get_path(toks, m))) for m in matches]

    def path_from_token_sequences(self, patname, toks, first_only=False):
        paths = []
        for seq in toks:
            paths += self.path_from_token_sequence(patname, seq, first_only)
        return paths

    def extract_from_token_sequence(self, patname, toks, first_only=False):
        if first_only:
            m = self.search(patname, toks)
            if m:
                return self.normalized_extraction(toks, m)
            else:
                return None
        else:
            matches = self.scan(patname, toks)
            return [self.normalized_extraction(toks, m) for m in matches]

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

    # TODO There are several type warnings in this method.
    # It may be out of date and need updating.
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
        tag_queues = [deque() for _ in range(len(matches))]
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

    # TODO: add unit test once
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
        return [(toks.find_paths(m.begin, m.end-1), self.normalized_extraction(toks, m))
                for m in matches]

    def dpaths_from_token_sequences(self, patname, toks):
        dpaths = []
        for seq in toks:
            dpaths += self.dpaths_from_token_sequence(patname, seq)
        return dpaths

    def tokens(self, text):
        toks = self.tokr.tokens(text)
        return [tok for tok in toks]

    def tokens_from_file(self, fname):
        text = self.file_contents(fname)
        return self.tokens(text)

    def present(self, patname, text, useSentencer=False):
        if not useSentencer:
            toks = self.tokr.tokens(text)
            return self.search(patname, toks)
        # TODO:  Test and refactor this code.  Hastily added to assist in an evaluation
        sentr = self.get_sentr()
        for sentence in sentr.sentences(text):
            toks = sentence.tokens()
            result = self.search(patname, toks)
            if result:
                return result
        return False

    def get_sentr(self):
        if hasattr(self, "sentr"):
            return self.sentr
        else:
            self.sentr = Sentencer(blank_line_terminals=True, tokenizer=self.tokr, skip_initial_regex='[^a-zA-Z]+')
            return self.sentr

    def present_in_file(self, patname, fname):
        text = self.file_contents(fname)
        return self.present(patname, text)

    def markup_file(self, patname, fname):
        text = self.file_contents(fname)
        return self.markup(patname, text)

    def extract_from_file(self, patname, fname, first_only=False):
        text = self.file_contents(fname)
        return self.extract(patname, text, first_only)
