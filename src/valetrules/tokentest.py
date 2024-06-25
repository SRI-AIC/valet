from abc import abstractmethod
from collections import Counter, defaultdict
import os.path
import random
import re
from typing import Iterable, Optional, Set, Union, TYPE_CHECKING, cast

from ordered_set import OrderedSet

from nlpcore.dbfutil import GenericException, SimpleClass
from nlpcore.annotator import Requirement

from .expression import Expression
from .extractor import Extractor
from .match import FAMatch
from .query import OneOfQuery, AndQuery, OrQuery, NotQuery
from .radius import TermRadius
if TYPE_CHECKING:
    from .manager import VRManager


class TokenTest(Extractor, SimpleClass):
    """Abstract base class for token tests."""

    # This exists just to default the manager.
    # See comments at Extractor ctor; prefer not to default it there.
    def __init__(self, manager: Optional['VRManager'] = None, **kwargs):
        super().__init__(manager, **kwargs)

    # These methods are intended to have the same behavior as for FAs
    # I presume that means the scan and matches methods?
    def scan(self, toks, start=0, end=None, substitutions=None):
        """Generate all matches within the indicated bounds."""
        if end is None:
            end = len(toks)
        for i in range(start, end):
            if self.matches_at(toks, i, substitutions):
                yield FAMatch(seq=toks, begin=i, end=i+1, name=self.name)

    def matches(self, toks, start=0, end=None, substitutions=None):
        """Generate one match if possible at the given starting point."""
        if end is None:
            end = len(toks)
        if start < end:
            if self.matches_at(toks, start, substitutions):
                yield FAMatch(seq=toks, begin=start, end=start+1, name=self.name)

    # There are two different methods next basically becase FAs can only match
    # FORWARD TOKEN BY TOKEN, whereas ArcFAs can JUMP AROUND via DEPENDENCY
    # LINKS.

    @abstractmethod
    def matches_at(self, toks, i, substitutions) -> Union[str, bool]:
        """Used by non-Arc FAs."""
        raise NotImplementedError()

    # Default implementation.
    def matches_token(self, tok, substitutions=None) -> Union[str, bool]:
        """Used by ArcFAs."""
        # E.g., see LookupTokenTest, where the info needed must be looked up
        # by token index.
        raise GenericException(msg=f"{self.__class__.__name__} can't match a raw token")

    # The tally stuff seems to be about tracking stats when recognizing,
    # so that generation can generate in a way that reflects those stats
    # (rather than choosing uniformly among alternatives).
    def seed(self, tseq):
        if not hasattr(self, 'tally'):
            self.tally = Counter()
        self.tally.update(t for i, t in enumerate(tseq) if self.matches_at(tseq, i, substitutions=None))

    @abstractmethod
    def testlabel(self):
        pass

    @abstractmethod
    def dump(self, indent=0):
        pass

    def generate(self, symbol) -> str:
        if not hasattr(self, 'tally'):
            return "<%s %s>" % (self.testlabel(), symbol)
        total = sum(self.tally.values())
        if total == 0:
            return "<%s %s>" % (self.testlabel(), symbol)
        which = random.randint(0, total - 1)
        subtot = 0
        items = list(self.tally.items())
        for t, count in items:
            subtot += count
            if subtot > which:
                return t
        return items[-1][0]

    # TODO What are the query methods all about?
    def query(self):
        return None


class AnyTokenTest(TokenTest):
    """Implements the built-in ANY token test that matches any token."""

    def matches_token(self, tok, substitutions=None):
        return True

    def matches_at(self, toks, i, substitutions):
        return True

    def testlabel(self):
        return "ANY"

    def dump(self, indent=0):
        print("%sANY" % (' ' * indent))


class RegexTokenTest(TokenTest):
    # This is an instance variable type declaration.
    # Since it's not assigned to in __init__, we can't declare it there.
    re: str
    case_insensitive: bool

    # Since we need an init method, but not a manager, we need to default
    # the manager, or have caller pass it as None.
    # Same for other TokenTest subclass types below (Radius, Membership, Substring).
    def __init__(self, manager: Optional['VRManager'] = None, **kwargs):
        super().__init__(manager, **kwargs)
        self._default('case_insensitive', False)
        self.compiled_re = re.compile(self.re, flags=(re.I if self.case_insensitive else 0))

    def matches_token(self, tok, substitutions=None):
        return bool(self.compiled_re.search(tok))

    def matches_at(self, toks, i, substitutions):
        return self.matches_token(toks[i])

    def testlabel(self):
        return "RE"

    def dump(self, indent=0):
        flag = '(i)' if self.case_insensitive else ''
        print("%sRE%s %s" % ((' ' * indent), flag, self.re))


class RadiusTokenTest(TokenTest):

    # The manager is optional here because it's held by the TermRadius,
    # but we can't default it to None because we can't have a non-default
    # param radius after a default param.
    def __init__(self, manager: Optional['VRManager'], radius: TermRadius, **kwargs):
        super().__init__(manager, **kwargs)
        self.radius = radius

    def matches_token(self, tok, substitutions=None):
        return self.radius.encloses(tok.lower())

    def matches_at(self, toks, at, substitutions):
        return self.matches_token(toks[at])

    def testlabel(self):
        return "RAD"

    def dump(self, indent=0):
        print("%sRAD" % (' ' * indent))

    def requirements(self, substitutions=None):
        return set([Requirement.EMBEDDINGS])


class MembershipTokenTest(TokenTest):
    members: OrderedSet[str]
    case_insensitive: bool
    stemming: bool

    def __init__(self, manager: Optional['VRManager'] = None,
                 members: Iterable[str] = [],
                 case_insensitive: bool = False, stemming: bool = False,
                 **kwargs):
        super().__init__(manager, **kwargs)
        self.case_insensitive = case_insensitive
        self.stemming = stemming
        if self.case_insensitive:
            self.members = OrderedSet(member.lower() for member in members)
        else:
            self.members = OrderedSet(members)
        # if self.stemming:
        #     self.members.add()  # not sure what this was, but don't add to default arg singleton

    def matches_token(self, tok, substitutions=None):
        if self.case_insensitive:
            tok = tok.lower()
        return tok in self.members

    def matches_at(self, toks, at, substitutions):
        if self.stemming:
            if not hasattr(toks, 'get_token_annotation'):
                raise GenericException(msg="Lemma is not available")
                # return self.matches_token(toks[at])
            lemma = toks.get_token_annotation("lemma", at)
            if self.case_insensitive:
                lemma = lemma.lower()
            return lemma in self.members
        return self.matches_token(toks[at])

    def testlabel(self):
        return "TAB"

    def generate(self, symbol) -> str:
        if not hasattr(self, 'tally'):
            members = list(self.members)
            idx = random.randint(0, len(members) - 1)
            return members[idx]
        else:
            return super().generate(symbol)

    def dump(self, indent=0):
        print("%sTAB: %s" % ((' ' * indent), self.members))

    def query(self):
        return OneOfQuery(self.members)


# Note FWIW that this will never complain about typos in the label,
# since we don't keep a set of valid labels.
# E.g., if you have lemmax[run] instead of lemma[run] by mistake.
class LookupTokenTest(TokenTest):
    """
    Works by querying the token sequence for information put there
    by a 3rd-party tool.  Token sequence should be instance of
    AnnotatedTokenSequence.
    """
    label: str
    members: Set[str]

    def matches_token(self, tok, substitutions=None):
        raise GenericException(msg="Lookup test can't match raw token")

    def matches_at(self, toks, at, substitutions):
        if not hasattr(toks, 'get_token_annotation'):
            return False
        annotation = toks.get_token_annotation(self.label, at)
        if annotation is None:
            return False
        if isinstance(annotation, set):
            return len(annotation.intersection(self.members)) > 0
        else:
            return annotation in self.members

    def testlabel(self):
        return "LU"

    def dump(self, indent=0):
        print("%sLU: %s" % ((' ' * indent), self.members))

    def requirements(self, substitutions=None):
        label = self.label
        if label == 'pos':
            return set([Requirement.POS])
        if label == 'ner':
            return set([Requirement.NER])
        if label == 'lemma':
            return set([Requirement.LEMMA])
        return set()


class SubstringTokenTest(TokenTest):
    substring: str
    case_insensitive: bool

    def __init__(self, manager: Optional['VRManager'] = None, **kwargs):
        super().__init__(manager, **kwargs)
        self._default('case_insensitive', False)
        if self.case_insensitive:
            self.substring = self.substring.lower()

    def matches_token(self, tok, substitutions=None):
        if self.case_insensitive:
            tok = tok.lower()
        return tok.find(self.substring) != -1

    def matches_at(self, toks, at, substitutions):
        return self.matches_token(toks[at])

    def testlabel(self):
        return "SUB"

    def dump(self, indent=0):
        print("%sSUB: %s" % ((' ' * indent), self.substring))


class LearningTokenTest(TokenTest):
    file: str

    def __init__(self, manager: Optional['VRManager'], **kwargs):
        from .extml import MLPExtractor
        super().__init__(manager, **kwargs)
        model_path = self.manager.model_path(self.file)
        if os.path.isfile(model_path):
            self.extractor = MLPExtractor.load(model_path)
        else:
            self.extractor = MLPExtractor(self.file, self.manager.embedding)

    def matches_token(self, tok, substitutions=None):
        raise GenericException(msg="Learning token test can't match a raw token")

    def _example(self, toks, at):
        from .extml import Example
        # This is a bit of a kludge. To avoid having to recreate examples
        # over and over, we cache them in the token sequence in a special
        # annotation layer.
        if not toks.has_annotations('examples'):
            toks.add_annotations('examples', [None for _ in toks])
        example = toks.get_token_annotation('examples', at)
        if example is None:
            example = Example(self.extractor, toks, at, at)
            toks.set_token_annotation('examples', at, example)
        return example

    def matches_at(self, toks, at, substitutions):
        return self.extractor.score(self._example(toks, at)) > 0

    def train(self, toks, at, positive):
        if self.extractor.add_example(self._example(toks, at), positive):
            self.extractor.train()
            self.extractor.save(self.manager.model_path(self.file))
            return True
        else:
            return False

    def testlabel(self):
        return "LRN"

    def dump(self, indent=0):
        print("%sLRN" % (' ' * indent))


class ReferenceTokenTest(TokenTest):
    patname: str

    def __init__(self, patname: str, manager: Optional['VRManager'] = None, **kwargs):
        super().__init__(manager, **kwargs)
        self.patname = patname

    def matches_token(self, tok, substitutions=None):
        patname, ext, type_, merged_substitutions = self.manager.substitute_and_lookup(self.patname, substitutions)
        if type_ != "test":
            raise GenericException(f"In token test {self.name}, {self.patname} (-> {patname}) should be a token test, but is a {self.manager.extractor_type_to_long_name(type_)}")
        ext = cast(TokenTest, ext)
        if ext.matches_token(tok, merged_substitutions):
            # See comment in matches_at().
            # The reasoning there might not apply completely here,
            # inasmuch as there can be different arc matches from "at",
            # whereas for phrase matches a token test always goes to
            # the next token.
            # However, there's LITTLE POINT in using token tests in
            # parse expression to begin with, and we ALSO seem to have
            # DECIDED not to track such tokentest submatches there
            # (unlike in phrase expressions, where we do).
            return patname
        else:
            return False

    def matches_at(self, toks, at, substitutions):
        patname, ext, type_, merged_substitutions = self.manager.substitute_and_lookup(self.patname, substitutions)
        if type_ != "test":
            raise GenericException(f"In token test {self.name}, {self.patname} (-> {patname}) should be a token test, but is a {self.manager.extractor_type_to_long_name(type_)}")
        ext = cast(TokenTest, ext)
        if ext.matches_at(toks, at, merged_substitutions):
            # Changing the contract a little to track any internal matches
            # by reference.
            # This (abstract) method [NOW] can return True, False, or the
            # string-valued name of a sub-test.
            # The comment here USED TO say basically "or a SET of string-valued
            # names from sub-tests in case of internal references", and WAS
            # RETURNING {patname}, but no callers are using the result
            # except for its truthiness.
            #
            # AFAICT this might have been anticipating creating submatches
            # for any sub-tests of a token test.
            # However, we seem to have DECIDED that while phrase/parse
            # matches will record submatches that are tokentest matches,
            # tokentest matches will not record submatches of other
            # tokentests.
            # That potentially could be done with either reference tests
            # (referencing one other test) or booleans (potentially referencing
            # multiple other tests).
            #
            # That decision seems reasonable, since while it makes sense to
            # record token test submatches of a phrase/parse expression match,
            # since those are typically SUB-PARTS of a larger match, such a set
            # of token test matches would all have the same 1-token extent,
            # so there's NOT MUCH POINT; they're all basically the SAME MATCH.
            #
            # So this might as well return True going forward, but I'm leaving
            # it for now, partly to relate to comments in caller
            # TestTransition's matches() and arc_matches().
            return patname
        else:
            return False

    def testlabel(self):
        return "REF"

    def generate(self, symbol) -> str:
        if not hasattr(self, 'tally'):
            try:
                ext, typ, _ = self.manager.lookup_extractor(self.patname)
            except Exception:
                raise GenericException(msg="Not a token test name: %s" % self.patname)
            if typ != 'test':
                raise GenericException(msg="Not a token test name: %s" % self.patname)
            return ext.generate(symbol)
        else:
            return super().generate(symbol)  # TODO?

    def dump(self, indent=0):
        print("%sREF %s" % ((' ' * indent), self.patname))

    def query(self):
        patname = self.manager.get_test(self.patname)  # TODO
        return patname.query()

    def requirements(self, substitutions=None):
        _, ext, _, merged_substitutions = self.manager.substitute_and_lookup(self.patname, substitutions)
        return ext.requirements(merged_substitutions)

    def references(self):
        return OrderedSet((self.patname,))


class AndTest(TokenTest):
    subs: Iterable[TokenTest]  # at least 2

    def matches_token(self, tok, substitutions=None):
        for test in self.subs:
            if not test.matches_token(tok, substitutions):
                return False
        return True

    def matches_at(self, toks, at, substitutions):
        for test in self.subs:
            if not test.matches_at(toks, at, substitutions):
                return False
        return True

    def testlabel(self):
        return "AND"

    def dump(self, indent=0):
        print("%sAND" % (' ' * indent))
        for s in self.subs:
            s.dump(indent+3)

    def query(self):
        subqueries = [s.query() for s in self.subs]
        subqueries = [q for q in subqueries if q is not None]
        if len(subqueries) == 0:
            return None
        return AndQuery(subqueries)

    def requirements(self, substitutions=None):
        req = set()
        for sub in self.subs:
            req |= sub.requirements(substitutions)
        return req

    def references(self):
        refs = OrderedSet()
        for test in self.subs:
            refs |= test.references()
        return refs


class OrTest(TokenTest):
    subs: Iterable[TokenTest]  # at least 2

    def matches_token(self, tok, substitutions=None):
        for test in self.subs:
            if test.matches_token(tok, substitutions):
                return True
        return False

    def matches_at(self, toks, at, substitutions):
        for test in self.subs:
            if test.matches_at(toks, at, substitutions):
                return True
        return False

    def testlabel(self):
        return "OR"

    def dump(self, indent=0):
        print("%sOR" % (' ' * indent))
        for s in self.subs:
            s.dump(indent+3)

    def query(self):
        subqueries = [s.query() for s in self.subs]
        subqueries = [q for q in subqueries if q is not None]
        if len(subqueries) == 0:
            return None
        return OrQuery(subqueries)

    def requirements(self, substitutions=None):
        req = set()
        for sub in self.subs:
            req |= sub.requirements(substitutions)
        return req

    def references(self):
        refs = OrderedSet()
        for test in self.subs:
            refs |= test.references()
        return refs


class NotTest(TokenTest):
    arg: TokenTest

    def matches_token(self, tok, substitutions=None):
        return not self.arg.matches_token(tok, substitutions)

    def matches_at(self, toks, at, substitutions):
        return not self.arg.matches_at(toks, at, substitutions)

    def testlabel(self):
        return "NOT"

    def dump(self, indent=0):
        print("%sNOT" % (' ' * indent))
        self.arg.dump(indent + 3)

    def query(self):
        subquery = self.arg.query()
        if subquery is None:
            return None
        return NotQuery(subquery)

    def requirements(self, substitutions=None):
        return self.arg.requirements(substitutions)

    def references(self):
        return self.arg.references()


class TokenTestExpression(Expression):
    token_expression: str
    toks: list

    def __init__(self, expr: str, manager: Optional['VRManager'], **kwargs):
        super().__init__(expr, manager, **kwargs)
        self._default('token_expression',
                      r'{.*?}\d+(?:\.\d*)|{.*?}i?|\w+\[.*?\]|/\S+?/i?|<\S+>i?|[&@]\w+(?:\.\w+)?|!\w+|\(|\)|\S+')

    # Why is this the only Expression.tokenize method that uses DOTALL
    # (allows matching newline)?
    # I guess because we want to allow token tests to match newlines.
    def tokenize(self, expr):
        return re.findall(self.token_expression, expr, re.DOTALL)

    def parse(self) -> TokenTest:
        # Special case. This is a learning token test, which can't
        # be combined with other token tests.
        m = re.match(r'\s*(!(\w+))\s*$', self.expr)
        if m:
            return LearningTokenTest(file=m.group(2), manager=self.manager)
        self.toks = self.tokenize(self.expr)
        # print(self.toks)
        test = self.orexpr()
        if len(self.toks) > 0:
            raise GenericException(msg="Extra tokens starting with '%s' in token test expression '%s'"
                                       % (self.toks, self.expr))
        return test

    # orexpr -> andexpr | andexpr 'or' andexpr
    def orexpr(self) -> TokenTest:
        orexpr = []
        test = self.andexpr()
        if test:
            orexpr.append(test)
        while len(self.toks) and self.toks[0] == 'or':
            self.toks.pop(0)
            orexpr.append(self.andexpr())
        if len(orexpr) == 0:
            raise GenericException(msg="Empty 'or' expression in token test expression '%s'"
                                   % self.expr)
        if len(orexpr) > 1:
            return OrTest(subs=orexpr, manager=self.manager)
        else:
            return orexpr[0]

    # andexpr -> notexpr | notexpr 'and' notexpr
    def andexpr(self) -> TokenTest:
        andexpr = []
        test = self.notexpr()
        if test:
            andexpr.append(test)
        while len(self.toks) and self.toks[0] == 'and':
            self.toks.pop(0)
            andexpr.append(self.notexpr())
        if len(andexpr) == 0:
            raise GenericException(msg="Empty 'and' expression in token test expression '%s'"
                                   % self.expr)
        if len(andexpr) > 1:
            return AndTest(subs=andexpr, manager=self.manager)
        else:
            return andexpr[0]

    # notexpr -> atom | 'not' atom
    def notexpr(self) -> Optional[TokenTest]:
        if len(self.toks) == 0:
            return None
        notted = False
        if self.toks[0] == 'not':
            notted = True
            self.toks.pop(0)
        test = self.atom()
        if test is None:
            raise GenericException(msg="Missing argument starting at '%s' in token test expression '%s'"
                                   % (self.toks[0], self.expr))
        if notted:
            return NotTest(arg=test, manager=self.manager)
        else:
            return test

    # atom -> /REGEX/ | <SUBSTRING> | {MEMBERSHIP} | &REF | LOOKUP[] | '(' orexpr ')'
    def atom(self) -> Optional[TokenTest]:

        def get_members_from_file(members):
            with open(members) as infile:
                return [x.strip() for x in infile]

        if len(self.toks) == 0:
            return None
        tok = self.toks.pop(0)
        # Nested expression
        if tok == '(':
            test = self.orexpr()
            if len(self.toks) == 0 or self.toks[0] != ')':
                raise GenericException(msg="Unbalanced '(' in token test expression '%s'"
                                       % self.expr)
            self.toks.pop(0)
            return test

        # Radius
        m = re.match(r'{(.*)}(\d+(?:\.\d*)?)(a?)', tok, re.DOTALL)
        if m:
            members = m.group(1)
            members = re.findall(r'\S+', members)
            radius = float(m.group(2))
            match_all = 'a' in m.group(3)
            radius_obj = TermRadius(self.manager.expander, radius, terms=set(members), match_any=not match_all)
            return RadiusTokenTest(manager=None, radius=radius_obj)

        # Membership
        # TODO? This code has a lot of duplication with VRManager.import_token_tests()
        # in manager.py.
        # I presume 'i?' is here twice to allow either order "is" or "si".
        m = re.match(r'([fcj]?){(.*)}(i?s?i?)$', tok, re.DOTALL)
        if m:
            isfile = m.group(1)
            members = m.group(2)
            insens = m.group(3) and 'i' in m.group(3)
            stemming = m.group(3) and 's' in m.group(3)
            if isfile:
                # Compare to the code in VRManager.import_token_tests(),
                # which DOES implement both the "c" and "j" cases,
                # which define MULTIPLE token tests.
                # I think the problem here with the "c" and "j" cases is that
                # here in TokenTestExpression.atom() we're just parsing
                # the expression on the RHS of a single rule statement,
                # and we're just returning a single TokenTest instance,
                # not (say) a set of (name, instance) tuples.
                # TODO? It might be time to drop all this here.
                if isfile == 'c':  # cluster
                    (labelfile, clusterfile) = [x.strip() for x in members.partition(";")]
                    with open(labelfile) as infile:
                        labels = dict(enumerate([x.strip() for x in infile]))
                    memberships = defaultdict(OrderedSet)
                    with open(clusterfile) as infile:
                        for (number, line) in enumerate(infile):
                            cluster = line.strip()
                            memberships[cluster].add(labels[number])
                    # Note this variable does not get used.
                    tests = [MembershipTokenTest(members=membs, case_insensitive=insens, stemming=stemming)
                             for (cluster, membs) in memberships.items()]
                    raise GenericException(msg="Clustering flag 'c' is not supported on token tests defined with the token test delimiter ':'")
                elif isfile == 'j':  # json
                    raise GenericException(msg="JSON flag 'j' is not supported on token tests defined with the token test delimiter ':'")
                else:  # 'f'
                    # The 'f' form IS documented.
                    path = self.manager.resolve_import_path(members)
                    members = get_members_from_file(path)
            else:
                members = re.findall(r'\S+', members)
            return MembershipTokenTest(members=members, case_insensitive=insens, stemming=stemming)

        # Substring
        m = re.match(r'<(.*)>(i?)$', tok)
        if m:
            substring = m.group(1)
            insens = m.group(2)
            return SubstringTokenTest(substring=substring,
                                      case_insensitive=insens)

        # Regular expression
        m = re.match(r'/(.*)/(i?)$', tok)
        if m:
            regex = m.group(1)
            insens = m.group(2)
            return RegexTokenTest(re=regex, case_insensitive=insens)

        # Reference
        m = re.match(r'[&@]((\w|\.)+)$', tok)
        if m:
            patname = m.group(1)
            return ReferenceTokenTest(patname=patname, manager=self.manager)

        # Lookup
        m = re.match(r'(\w+)\[(.*)]$', tok, re.DOTALL)
        if m:
            label = m.group(1)
            members = m.group(2)
            members = re.findall(r'\S+', members)
            return LookupTokenTest(label=label,
                                   members=set(members))

        raise GenericException(msg="Unparsable atom '%s' in token test expression '%s'"
                               % (tok, self.expr))
