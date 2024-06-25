import re
from typing import Optional, Tuple, TYPE_CHECKING

from nlpcore.dbfutil import GenericException, SimpleClass
from .coordinator import \
    Coordinator, BaseCoordinator, \
    MatchCoordinator, SelectCoordinator, \
    FilterCoordinator, PrefixFilterCoordinator, SuffixFilterCoordinator, \
    NearFilterCoordinator, PrecedesFilterCoordinator, FollowsFilterCoordinator, \
    CountFilterCoordinator, \
    IntersectionCoordinator, UnionCoordinator, DiffCoordinator, \
    ContainCoordinator, ContainedByCoordinator, OverlapCoordinator, \
    HasPathFilterCoordinator, ConnectsCoordinator, \
    WhenCoordinator, \
    WidenCoordinator, MergeCoordinator, \
    WhenHandler, OrHandler, AndHandler, NotHandler, RefHandler
from .expression import Expression
if TYPE_CHECKING:
    from .manager import VRManager

# TODO Update this for new inversion syntax, NFeedCoordinators,
# WhenCoordinator, etc.
# ssexp -> fexp | mexp | '_'
# fexp -> fop '(' name ',' inv ',' ssexp ')'
# pexp -> pop '(' name ',' inv ',' prox ',' ssexp ')'
# mexp -> mop '(' name ',' ssexp ')'
# jexp -> jop '(' ssexp ',' ssexp ')'
# cexp -> cop '(' name ',' ssexp ',' ssexp ')'
# fop -> 'filter' | 'prefix' | 'suffix'
# pop -> 'near' | 'precedes' | 'follows'
# mop -> 'match' | 'select'
# jop -> 'inter' | 'union' | 'contains' | 'contained_by' | 'overlaps'
# cop -> 'connects'
# name -> \w+
# inv -> '1' | '0'

"""
Provides the CoordinatorExpression class, which is responsible for
parsing coordinator expressions into a tree of instances of the Coordinator
class or subclasses (provided by the coordinator module) mirroring the
structure of the expressions.
"""


class CoordinatorExpression(Expression):
    token_expression: str
    toks: list

    operators = {
        'match': 'match_args',
        'select': 'match_args',
        'filter': 'filter_args',
        'prefix': 'filter_args',
        'suffix': 'filter_args',
        'near': 'prox_filter_args',
        'precedes': 'prox_filter_args',
        'follows': 'prox_filter_args',
        'count': 'prox_filter_args',  # not really proximity, but takes args similar to that
        'inter': 'nary_args',
        'union': 'nary_args',
        'diff': 'nary_args',
        'contains': 'join_args',
        'contained_by': 'join_args',
        'overlaps': 'join_args',
        'haspath': 'haspath_args',
        'connects': 'connects_args',
        'when': 'when_args',
        'widen': 'unit_args',
        'merge': 'unit_args',
        }

    def __init__(self, expr: str, manager: Optional['VRManager'], **kwargs):
        super().__init__(expr, manager, **kwargs)
        self._default('token_expression', r'\w+(?:\.\w+)*|\S')
        # Dayne is not sure what the additional (vs above) initial part here
        # was about; but related to "label" below.
        # I later figured out that this is used in CoordMatch.operator_map
        # which is maybe called from vrconsole, but since that may well
        # be obsolete, leave it commented for now.
        # self._default('token_expression', r'(?:\w+(?: ?\: ?\w+ ?)? ?= ?)?\w+(?:\.\w+)*|\S')

    def tokenize(self, expr):
        return re.findall(self.token_expression, expr)

    def parse(self) -> Coordinator:
        """
        Parse coordinator expression, recursing into subexpresssions,
        returning a hierarchically connected set of Coordinator (and subclass)
        instances.
        """
        self.toks = self.tokenize(self.expr)
        ext = self._parse()
        if len(self.toks) > 0:
            raise GenericException(msg="Extra tokens starting with '%s' in coordinator expression '%s'" % (self.toks[0], self.expr))
        return ext

    # This statefully consumes tokens from self.toks.
    def _parse(self) -> Coordinator:
        """
        Parse tokenized coordinator expression, recursing into subexpresssions,
        returning a hierarchically connected set of Coordinator (and subclass)
        instances.
        """

        op = self.toks.pop(0)  # usually an operator name like match, select, ...

        # This is related to the old token_expression regexp above.
        label = None  # passed to coordinator ctors, but not used by them
        # if "=" in op:
        #    label, equalsign, op = op.partition("=")

        # Base match stream
        if op == '_':
            return BaseCoordinator(manager=self.manager)

        # If the lookahead token is not '(', interpret as named extractor
        # applied to full tseq (or rather, to whatever _ represents in the
        # current context).
        # I.e., interpret a token like "extractor" that is permissible as
        # an extractor name as a shorthand for match(extractor, _).
        if (len(self.toks) == 0 or self.toks[0] != '(') and self.match_extractor_name(op):
            return MatchCoordinator(manager=self.manager, patname=op, feed=BaseCoordinator(manager=self.manager),
                                    label=label)

        # Otherwise it involves an operator expression
        try:
            args_method = CoordinatorExpression.operators[op]
        except KeyError:
            raise GenericException(msg="Illegal operator '%s' in coordinator expression '%s'" % (op, self.expr))

        tok = self.toks.pop(0)
        if tok != '(':
            raise GenericException(msg="Bad arg list opener '%s' in coordinator expression '%s'" % (tok, self.expr))

        # A tuple, the length and structure of which depends on the op
        args: Tuple = getattr(self, args_method)()  # will recurse to handle subexpressions

        tok = self.toks.pop(0)
        if tok != ')':
            raise GenericException(msg="Bad arg list terminator '%s' in coordinator expression '%s'" % (tok, self.expr))

        if op == 'match':
            return MatchCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], label=label)
        elif op == 'select':
            return SelectCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], label=label)
        elif op == 'filter':
            return FilterCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'prefix':
            return PrefixFilterCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'suffix':
            return SuffixFilterCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'near':
            return NearFilterCoordinator(
                manager=self.manager,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'precedes':
            return PrecedesFilterCoordinator(
                manager=self.manager,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'follows':
            return FollowsFilterCoordinator(
                manager=self.manager,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'count':
            return CountFilterCoordinator(
                manager=self.manager, patname=args[0], feed=args[1], count=args[2], inverted=args[3], label=label)
        elif op == 'inter':
            return IntersectionCoordinator(
                manager=self.manager, feeds=args, label=label)
        elif op == 'union':
            return UnionCoordinator(
                manager=self.manager, feeds=args, label=label)
        elif op == 'diff':
            return DiffCoordinator(
                manager=self.manager, feeds=args, label=label)
        elif op == 'contains':
            return ContainCoordinator(
                manager=self.manager, left_feed=args[0], right_feed=args[1], label=label)
        elif op == 'contained_by':
            return ContainedByCoordinator(
                manager=self.manager, left_feed=args[0], right_feed=args[1], label=label)
        elif op == 'overlaps':
            return OverlapCoordinator(
                manager=self.manager, left_feed=args[0], right_feed=args[1], label=label)
        # TODO This is not documented, but perhaps the args should be
        # consistent with connects, which is documented?
        elif op == 'haspath':
            return HasPathFilterCoordinator(
                manager=self.manager,
                left_feed=args[0],
                right_feed=args[1],
                dpath=args[2],
                direction=None,
                label=label)
        elif op == 'connects':
            return ConnectsCoordinator(
                manager=self.manager,
                left_feed=args[1],
                right_feed=args[2],
                patname=args[0],
                label=label)
        # TODO This looks leftover?
        elif op == 'connects_down':
            return ConnectsCoordinator(
                manager=self.manager,
                left_feed=args[0],
                right_feed=args[1],
                dpath=args[2],
                direction="down",
                label=label)
        elif op == 'when':
            return WhenCoordinator(
                manager=self.manager, boolean=args[0], feed=args[1], label=label)
        # The rest are old and/or experimental, and not documented.
        # TODO? Note the warnings on patname=None; code would need updating.
        elif op == 'widen':
            return WidenCoordinator(manager=self.manager, patname=None, feed=args[0], label=label)
        elif op == 'merge':
            return MergeCoordinator(manager=self.manager, patname=None, feed=args[0], label=label)
#        elif op == 'eval':
#            return EvalCoordinator(manager=self.manager, feedname=args[0], label=label)

    @staticmethod
    def match_extractor_name(sel):
        """Is the token interpretable as an extractor name?"""
        return re.match(r'^\w+(?:\.\w+)*$', sel)

    def match_args(self) -> Tuple:

        name = self.toks.pop(0)
        m = self.match_extractor_name(name)
        if not m:
            raise illegal_extractor_name(name, self.expr)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)

        # Recurse
        ext = self._parse()

        return name, ext

    def filter_args(self) -> Tuple:

        name = self.toks.pop(0)
        m = self.match_extractor_name(name)
        if not m:
            raise illegal_extractor_name(name, self.expr)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)

        # Recurse
        ext = self._parse()

        invb = False

        if len(self.toks) > 0 and self.toks[0] == ',':
            self.toks.pop(0)
            kw = self.toks.pop(0)
            if kw != 'invert':
                raise invalid_inversion_flag(kw, self.expr)
            invb = True

        return name, ext, invb

    def prox_filter_args(self) -> Tuple:

        name = self.toks.pop(0)
        m = self.match_extractor_name(name)
        if not m:
            raise illegal_extractor_name(name, self.expr)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)

        param = self.toks.pop(0)
        try:
            param = int(param)
        except ValueError:
            raise not_non_negative_integer(param, self.expr) from None

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)

        # Recurse
        ext = self._parse()

        invb = False

        if len(self.toks) > 0 and self.toks[0] == ',':
            self.toks.pop(0)
            kw = self.toks.pop(0)
            if kw != 'invert':
                raise invalid_inversion_flag(kw, self.expr)
            invb = True

        return name, ext, param, invb

    def nary_args(self) -> Tuple:

        arg = self._parse()
        args = [arg]

        tok = self.toks.pop(0)
        while tok == ',':
            arg = self._parse()
            args.append(arg)
            tok = self.toks.pop(0)
        if tok != ')':
            raise improper_delimiter(tok, self.expr)
        self.toks.insert(0, tok)

        return tuple(args)

    def join_args(self) -> Tuple:

        # Recurse
        left = self._parse()

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)

        # Recurse
        right = self._parse()

        return left, right

    def haspath_args(self) -> Tuple:
        left = self._parse()
        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)
        right = self._parse()
        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)
        # dpath = self._parse()
        # print(self.toks)
        tok = self.toks.pop(0)
        if tok != '"' and tok != "'":
            raise GenericException(msg="No quoted dpath present near '%s'in coordinator expression '%s'" % (tok, self.expr))
        endtok = tok
        if endtok not in self.toks:
            raise GenericException(msg="No end quote in dpath present near '%s' in coordinator expression '%s'" % (tok, self.expr))
        dpath = []
        tok = self.toks.pop(0)
        while tok != endtok:
            dpath += [tok]
            tok = self.toks.pop(0)
        return left, right, dpath

    def connects_args(self) -> Tuple:
        name = self.toks.pop(0)
        m = self.match_extractor_name(name)
        if not m:
            raise illegal_extractor_name(name, self.expr)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)
        left = self._parse()  # recurse

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)
        right = self._parse()  # recurse

        return name, left, right

    def when_args(self) -> Tuple:
        when_expr = WhenExpression(self.manager)
        boolean = when_expr.parse(self.toks)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.expr)
        left = self._parse()  # recurse

        return boolean, left

    def eval_args(self) -> Tuple:
        name = self.toks.pop(0)
        return name,

    def unit_args(self) -> Tuple:

        # Single argument. Recurse.
        ext = self._parse()

        return ext,


# This is adapted from tokentest.TokenTestExpression.
# There's a fair amount of commonality in the and/or/not portions,
# so could conceivably extract a base class.
# It would have to be a "generic" class regarding the types returned,
# which would complicate attempts at type declarations.
# Here the type parameter value would be WhenHandler, and in
# TokenTestExpression the type parameter would be TokenTest.
#
# However, this is not a valetrules.Expression subclass.
# Although similar, it's a different kind of thing.
# It's not representing the complete expression on the RHS of a rule,
# but the boolean SUB-expression in the first arg of a when() coordinator.
class WhenExpression(SimpleClass):
    toks: list

    def __init__(self, manager: Optional['VRManager'], **kwargs):
        super().__init__(**kwargs)
        self.manager = manager

    def parse(self, toks) -> WhenHandler:
        self.toks = toks  # from the full expression, partly consumed
        self.orig_toks = list(toks)
        test = self.orexpr()
        return test

    # Rather a kludge, but perhaps good enough.
    def infer_expr(self):
        """Only works during parsing."""
        used_toks = self.orig_toks[0:len(self.orig_toks)-len(self.toks)]
        return " ".join(used_toks)

    # orexpr -> andexpr | andexpr 'or' andexpr
    def orexpr(self) -> WhenHandler:
        orexpr = []
        test = self.andexpr()
        if test:
            orexpr.append(test)
        while len(self.toks) and self.toks[0] == 'or':
            self.toks.pop(0)
            orexpr.append(self.andexpr())
        if len(orexpr) == 0:
            raise GenericException(msg="Empty 'or' expression in boolean expression '%s'"
                                   % self.infer_expr())
        if len(orexpr) > 1:
            return OrHandler(subs=orexpr, manager=self.manager)
        else:
            return orexpr[0]

    # andexpr -> notexpr | notexpr 'and' notexpr
    def andexpr(self) -> WhenHandler:
        andexpr = []
        test = self.notexpr()
        if test:
            andexpr.append(test)
        while len(self.toks) and self.toks[0] == 'and':
            self.toks.pop(0)
            andexpr.append(self.notexpr())
        if len(andexpr) == 0:
            raise GenericException(msg="Empty 'and' expression in boolean expression '%s'"
                                   % self.infer_expr())
        if len(andexpr) > 1:
            return AndHandler(subs=andexpr, manager=self.manager)
        else:
            return andexpr[0]

    # notexpr -> atom | 'not' atom
    def notexpr(self) -> Optional[WhenHandler]:
        if len(self.toks) == 0:
            return None
        notted = False
        if self.toks[0] == 'not':
            notted = True
            self.toks.pop(0)
        test = self.atom()
        if test is None:
            raise GenericException(msg="Missing argument starting at '%s' in boolean expression '%s'"
                                   % (self.toks[0], self.infer_expr()))
        if notted:
            return NotHandler(arg=test, manager=self.manager)
        else:
            return test

    # atom -> REF | '(' orexpr ')'
    def atom(self) -> Optional[WhenHandler]:

        if len(self.toks) == 0:
            return None
        tok = self.toks.pop(0)
        # Nested expression
        if tok == '(':
            test = self.orexpr()  # recurse
            if len(self.toks) == 0 or self.toks[0] != ')':
                raise GenericException(msg="Unbalanced '(' in boolean expression '%s'"
                                       % self.infer_expr())
            self.toks.pop(0)
            return test

        # You could imagine something like a boolean literal,
        # but there's probably no real need.

        # Reference
        m = re.match(r'\w+(?:\.\w+)*$', tok)
        if m:
            name = m.group(0)
            return RefHandler(patname=name, manager=self.manager)

        raise GenericException(msg="Unparsable atom '%s' in boolean expression '%s'"
                               % (tok, self.infer_expr()))


def illegal_extractor_name(tok, expr):
    return GenericException(msg="Illegal extractor name '%s' in coordinator expression '%s'" % (tok, expr))


def no_argument_delimiter(tok, expr):
    return GenericException(msg="No argument delimiter ',' before '%s' in coordinator expression '%s'" % (tok, expr))


def invalid_inversion_flag(tok, expr):
    return GenericException(msg="Invalid inversion flag '%s' in coordinator expression '%s'" % (tok, expr))


def not_non_negative_integer(tok, expr):
    return GenericException(msg="Expected non-negative integer (without sign) but got '%s' in coordinator expression '%s'" % (tok, expr))


def improper_delimiter(tok, expr):
    return GenericException(msg="Expected ',' or ')' but got '%s' in coordinator expression '%s'" % (tok, expr))
