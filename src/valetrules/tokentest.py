import re
import random
from collections import Counter, defaultdict
import os.path

from nlpcore.dbfutil import SimpleClass, GenericException
from nlpcore.annotator import Requirement

from .match import FAMatch
from .query import OneOfQuery, AndQuery, OrQuery, NotQuery
from .radius import TermRadius


class TokenTest(SimpleClass):

    def __init__(self, **args):
        super().__init__(**args)
        if not hasattr(self, 'name'):
            self.name = None

    # These methods are intended to have the same behavior as for FAs
    # I presume that means the scan and matches methods?
    def scan(self, toks, start=0, end=None):
        """Generate all matches within the indicated bounds."""
        if end is None:
            end = len(toks)
        for i in range(start, end):
            if self.matches_at(toks, i):
                yield FAMatch(seq=toks, begin=i, end=i+1, name=self.name)

    def matches(self, toks, start=0, end=None):
        """Generate one match if possible at the given starting point."""
        if end is None:
            end = len(toks)
        if start < end:
            if self.matches_at(toks, start):
                yield FAMatch(seq=toks, begin=start, end=start+1, name=self.name)

    def matches_at(self, toks, i):
        raise NotImplementedError()

    def seed(self, tseq):
        if not hasattr(self, 'tally'):
            self.tally = Counter()
        self.tally.update(t for i, t in enumerate(tseq) if self.matches_at(tseq, i))

    def generate(self, symbol):
        if not hasattr(self, 'tally'):
            return "<%s %s>" % (self.testlabel(), symbol)
        total = sum(self.tally.values())
        if total == 0:
            return "<%s %s>" % (self.testlabel(), symbol)
        which = random.randint(0, total - 1)
        subtot = 0
        items = list(self.tally.items())
        for t,count in items:
            subtot += count
            if subtot > which:
                return t
        return items[-1][0]

    def query(self):
        return None

    def requirements(self):
        return set()


class RegexTokenTest(TokenTest):

    def __init__(self, **args):
        TokenTest.__init__(self, **args)
        self._default('case_sensitive', True)

    def matches_token(self, tok):
        if self.case_sensitive:
            return re.search(self.re, tok)
        else:
            return re.search(self.re, tok, re.I)
    
    def matches_at(self, toks, i):
        return self.matches_token(toks[i])

    def testlabel(self):
        return "RE"

    def dump(self, indent=0):
        if self.case_sensitive:
            flag = ''
        else:
            flag = '(i)'
        print("%sRE%s %s" % ((' ' * indent), flag, self.re))


class RadiusTokenTest(TokenTest):

    def __init__(self, **args):
        TokenTest.__init__(self, **args)
        if 'radius' not in args:
            raise GenericException(msg="Missing radius object")

    def matches_token(self, tok):
        return self.radius.encloses(tok.lower())

    def matches_at(self, toks, at):
        return self.matches_token(toks[at])

    def testlabel(self):
        return "RAD"

    def dump(self, indent=0):
        print("%sRAD" % (' ' * indent))

    def requirements(self):
        return set([Requirement.EMBEDDINGS])


class MembershipTokenTest(TokenTest):

    def __init__(self, **args):
        TokenTest.__init__(self, **args)
        self._default('case_sensitive', True)
        self._default('stemming', False)
        if not self.case_sensitive:
            self.members = set(member.lower() for member in self.members)
        #if self.stemming:
        #    self.members.add()

    def matches_token(self, tok):
        if not self.case_sensitive:
            tok = tok.lower()
        return tok in self.members

    def matches_at(self, toks, at):
        if self.stemming:
            if not hasattr(toks, 'get_token_annotation'):
                raise GenericException(msg="Lemma is not available")
                #return self.matches_token(toks[at])
            lemma = toks.get_token_annotation("lemma", at)
            if not self.case_sensitive:
                lemma = lemma.lower()
            return lemma in self.members
        return self.matches_token(toks[at])

    def testlabel(self):
        return "TAB"

    def generate(self, symbol):
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

    def matches_token(self, tok):
        raise GenericException(msg="Lookup test can't match raw token")

    def matches_at(self, toks, at):
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

    def requirements(self):
        label = self.label
        if label == 'pos':
            return set([Requirement.POS])
        if label == 'ner':
            return set([Requirement.NER])
        if label == 'lemma':
            return set([Requirement.LEMMA])
        return set()


class SubstringTokenTest(TokenTest):

    def __init__(self, **args):
        TokenTest.__init__(self, **args)
        self._default('case_sensitive', False)
        if not self.case_sensitive:
            self.substring = self.substring.lower()

    def matches_token(self, tok):
        if not self.case_sensitive:
            tok = tok.lower()
        return tok.find(self.substring) != -1

    def matches_at(self, toks, at):
        return self.matches_token(toks[at])

    def testlabel(self):
        return "SUB"

    def dump(self, indent=0):
        print("%sSUB: %s" % ((' ' * indent), self.substring))


class LearningTokenTest(TokenTest):

    def __init__(self, **args):
        from .extml import MLPExtractor
        super().__init__(**args)
        model_path = self.manager.model_path(self.file)
        if os.path.isfile(model_path):
            self.extractor = MLPExtractor.load(model_path)
        else:
            self.extractor = MLPExtractor(self.file, self.manager.embedding)

    def matches_token(self, tok):
        raise GenericException(msg="Learning token test can't match a raw token")

    def _example(self, toks, at):
        from .extml import Example
        # This is a bit of a kludge.  To avoid having to recreate examples over and over, we cache them
        # in the token sequence in a special annotation layer.
        if not toks.has_annotations('examples'):
            toks.add_annotations('examples', [None for _ in toks])
        example = toks.get_token_annotation('examples', at)
        if example is None:
            example = Example(self.extractor, toks, at, at)
            toks.set_token_annotation('examples', at, example)
        return example

    def matches_at(self, toks, at):
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

    def matches_token(self, tok):
        ref = self.manager.get_test(self.ref)
        if ref.matches_token(tok):
            # Changing the contract a little to track any internal matches by reference.
            # This method now can return True, False, or a set of results from matching
            # sub-tests, which may yield string-valued names, in case of internal references.
            return {self.ref}
        else:
            return False

    def matches_at(self, toks, at):
        ref = self.manager.get_test(self.ref)
        if ref.matches_at(toks, at):
            # Changing the contract a little to track any internal matches by reference.
            # This method now can return True, False, or a set of results from matching
            # sub-tests, which may yield string-valued names, in case of internal references.
            return {self.ref}
        else:
            return False

    def testlabel(self):
        return "REF"

    def generate(self, symbol):
        if not hasattr(self, 'tally'):
            ref = self.manager.get_test(self.ref)
#            ref = self.manager.tests[self.name]
            return ref.generate(symbol)
        else:
            return super().generate(symbol)

    def dump(self, indent=0):
        print("%sREF %s" % ((' ' * indent), self.ref))

    def query(self):
        ref = self.manager.get_test(self.ref)
        return ref.query()

    def requirements(self):
        return self.manager.get_test(self.ref).requirements()


class AndTest(TokenTest):

    def matches_token(self, tok):
        for test in self.subs:
            if not test.matches_token(tok):
                return False
        return True

    def matches_at(self, toks, at):
        for test in self.subs:
            if not test.matches_at(toks, at):
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

    def requirements(self):
        req = set()
        for sub in self.subs:
            req |= sub.requirements()
        return req


class OrTest(TokenTest):

    def matches_token(self, tok):
        for test in self.subs:
            if test.matches_token(tok):
                return True
        return False

    def matches_at(self, toks, at):
        for test in self.subs:
            if test.matches_at(toks, at):
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

    def requirements(self):
        req = set()
        for sub in self.subs:
            req |= sub.requirements()
        return req

class NotTest(TokenTest):

    def matches_token(self, tok):
        return not self.arg.matches_token(tok)

    def matches_at(self, toks, at):
        return not self.arg.matches_at(toks, at)

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

    def requirements(self):
        return self.arg.requirements()


class TokenTestExpression(SimpleClass):

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self._default('token_expression', 
                      r'{.*?}\d+(?:\.\d*)|{.*?}i?|\w+\[.*?\]|/\S+?/i?|<\S+>i?|[&@]\w+(?:\.\w+)?|!\w+|\(|\)|\S+')

    def tokenize(self, str):
        return re.findall(self.token_expression, str, re.DOTALL)

    def parse(self, expr):
        self.string = expr
        # Special case.  This is a learning token test, which can't be combined with other token tests.
        m = re.match(r'\s*(!(\w+))\s*$', expr)
        if m:
            return LearningTokenTest(file=m.group(2), manager=self.manager)
        self.toks = self.tokenize(self.string)
        # print(self.toks)
        test = self.orexpr()
        if len(self.toks) > 0:
            raise GenericException(msg="Extra tokens starting with '%s' in token test expression '%s'" 
                                       % (self.toks, self.string))
        return test

    # orexpr -> andexpr | andexpr 'or' andexpr
    def orexpr(self):
        orexpr = []
        test = self.andexpr()
        if test:
            orexpr.append(test)
        while len(self.toks) and self.toks[0] == 'or':
            self.toks.pop(0)
            orexpr.append(self.andexpr())
        if len(orexpr) == 0:
            raise GenericException(msg="Empty 'or' expression in token test expression '%s'" 
                                   % self.string)
        if len(orexpr) > 1:
            return OrTest(subs=orexpr)
        else:
            return orexpr[0]

    # andexpr -> notexpr | notexpr 'and' notexpr
    def andexpr(self):
        andexpr = []
        test = self.notexpr()
        if test:
            andexpr.append(test)
        while len(self.toks) and self.toks[0] == 'and':
            self.toks.pop(0)
            andexpr.append(self.notexpr())
        if len(andexpr) == 0:
            raise GenericException(msg="Empty 'and' expression in token test expression '%s'"
                                   % self.string)
        if len(andexpr) > 1:
            return AndTest(subs=andexpr)
        else:
            return andexpr[0]

    # notexpr -> atom | 'not' atom
    def notexpr(self):
        if len(self.toks) == 0:
            return None
        notted = False
        if self.toks[0] == 'not':
            notted = True
            self.toks.pop(0)
        test = self.atom()
        if test is None:
            raise GenericException(msg="Missing argument starting at '%s' in token test expression '%s'"
                                   % (self.toks[0], self.string))
        if notted:
            return NotTest(arg=test)
        else:
            return test

    # atom -> /REGEX/ | <SUBSTRING> | {MEMBERSHIP} | &REF | LOOKUP[] | '(' orexpr ')'
    def atom(self):

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
                                       % self.string)
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
            return RadiusTokenTest(radius=radius_obj)

        # Membership
        # TODO? This code has a lot of duplication with VRManager.import_token_tests() 
        # in manager.py.
        # TODO why is 'i?' in here twice?
        m = re.match(r'([fcj]?){(.*)}(i?s?i?)$', tok, re.DOTALL)
        if m:
            isfile = m.group(1)
            members = m.group(2)
            insens = m.group(3) and 'i' in m.group(3)
            stemming = m.group(3) and 's' in m.group(3)
            if isfile:
                if isfile == 'c':
                    (labelfile,clusterfile) = [x.strip() for x in members.partition(";")]
                    with open(labelfile) as infile:
                        labels = dict(enumerate([x.strip() for x in infile]))
                    memberships = defaultdict(set)
                    with open(clusterfile) as infile:
                        for (number,line) in enumerate(infile):
                            cluster = line.strip()
                            memberships[cluster].add(labels[number])
                    # TODO not used
                    tests = [MembershipTokenTest(members=membs, case_sensitive=not insens, stemming=stemming)
                             for (cluster,membs) in memberships.items()]
                    # cluster
                elif isfile == 'j':
                    pass
                    # json
                else:
                    path = self.manager.resolve_import_path(members)
                    members = get_members_from_file(path)
            else:
                members = re.findall(r'\S+', members)
            return MembershipTokenTest(members=set(members), case_sensitive=not insens, stemming=stemming)

        # Substring
        m = re.match(r'<(.*)>(i?)$', tok)
        if m:
            substring = m.group(1)
            insens = m.group(2)
            return SubstringTokenTest(substring=substring, 
                                      case_sensitive=not insens)

        # Regular expression
        m = re.match(r'/(.*)/(i?)$', tok)
        if m:
            regex = m.group(1)
            ci = m.group(2)
            return RegexTokenTest(re=regex, case_sensitive=not ci)

        # Reference
        m = re.match(r'[&@]((\w|\.)+)$', tok)
        if m:
            name = m.group(1)
            return ReferenceTokenTest(ref=name, manager=self.manager)

        # Lookup
        m = re.match(r'(\w+)\[(.*)\]$', tok, re.DOTALL)
        if m:
            label = m.group(1)
            members = m.group(2)
            members = re.findall(r'\S+', members)
            return LookupTokenTest(label=label, 
                                   members=set(members))

        raise GenericException(msg="Unparsable atom '%s' in token test expression '%s'"
                               % (tok, self.string))
