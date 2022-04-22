import re

from nlpcore.dbfutil import SimpleClass, GenericException
from valetrules.coordinator import BaseCoordinator, MatchCoordinator, SelectCoordinator, \
    FilterCoordinator, PrefixFilterCoordinator, SuffixFilterCoordinator, \
    NearFilterCoordinator, PrecedesFilterCoordinator, FollowsFilterCoordinator, \
    CountFilterCoordinator, \
    SNearFilterCoordinator, SPrecedesFilterCoordinator, SFollowsFilterCoordinator, \
    IntersectionCoordinator, UnionCoordinator, ContainCoordinator, ContainedByCoordinator, OverlapCoordinator, \
    HasPathFilterCoordinator, ConnectsCoordinator, \
    WidenCoordinator, EvalCoordinator, DiffCoordinator, MergeCoordinator

# ssexp -> fexp | mexp | '_'
# fexp -> fop '(' ext ',' inv ',' ssexp ')'
# pexp -> pop '(' ext ',' inv ',' prox ',' ssexp ')'
# mexp -> mop '(' ext ',' ssexp ')'
# jexp -> jop '(' ssexp ',' ssexp ')'
# cexp -> cop '(' ext ',' ssexp ',' ssexp ')'
# fop -> 'filter' | 'prefix' | 'suffix'
# pop -> 'near' | 'precedes' | 'follows'
# mop -> 'match' | 'select'
# jop -> 'inter' | 'union' | 'contains' | 'contained_by' | 'overlaps'
# cop -> 'connects'
# ext -> \w+
# inv -> '1' | '0'

"""
Provides the CoordinatorExpression class, which is responsible for 
parsing coordinator expressions into a tree of instances of the Coordinator 
class or subclasses (provided by the coordinator module) mirroring the 
structure of the expressions.
"""

class CoordinatorExpression(SimpleClass):

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
        'snear': 'proxs_filter_args',
        'sprecedes': 'proxs_filter_args',
        'sfollows': 'proxs_filter_args',
#        'inter': 'join_args',
#        'union': 'join_args',
#        'diff': 'join_args',
        'inter': 'nary_args',
        'union': 'nary_args',
        'diff': 'nary_args',
        'contains': 'join_args',
        'contained_by': 'join_args',
        'overlaps': 'join_args',
        'haspath': 'haspath_args',
        'connects': 'connects_args',
        'widen': 'unit_args',
        'merge': 'unit_args',
        'eval' : 'eval_args',
        }

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self._default('token_expression', r'(?:\w+(?: ?\: ?\w+ ?)? ?= ?)?\w+(?:\.\w+)?|\S')
#        self._default('token_expression', r'\w+|\S')

    def tokenize(self, string):
        return re.findall(self.token_expression, string)

    def parse(self):
        self.toks = self.tokenize(self.string)
        sstream = self.seq_stream()
        if len(self.toks) > 0:
            raise GenericException(msg="Extra tokens starting with '%s' in coordinator expression '%s'" % (self.toks[0], self.string))
        return sstream

    def seq_stream(self):
        """
        Parse tokenized coordinator expression, recursing into subexpresssions,
        returning a hierarchically connected set of Coordinator (and subclass) 
        instances.
        """

        op = self.toks.pop(0)

        # TODO what is this about?
        label = None
        if "=" in op:
            label, equalsign, op = op.partition("=")

        # Input seq stream
        if op == '_':
            return BaseCoordinator(parent=self.parent)

        # If the lookahead token is not '(', interpret as named extractor applied to input.
        # I.e., interpret a token like "extractor" that is permissible as 
        # an extractor name as a shorthand for match(extractor, _).
        if (len(self.toks) == 0 or self.toks[0] != '(') and self.match_extractor_name(op):
            return MatchCoordinator(parent=self.parent, patname=op, feed=BaseCoordinator(parent=self.parent),
                                    label=label)

        # Otherwise it involves an op expression
        try:
            args_method = CoordinatorExpression.operators[op]
        except KeyError:
            raise GenericException(msg="Illegal operator '%s' in coordinator expression '%s'" % (op, self.string))

        tok = self.toks.pop(0)
        if tok != '(':
            raise GenericException(msg="Bad arg list opener '%s' in coordinator expression '%s'" % (tok, self.string))

        # A tuple, the length and structure of which depends on the op
        args = getattr(self, args_method)()  # will recurse to handle subexpressions

        tok = self.toks.pop(0)
        if tok != ')':
            raise GenericException(msg="Bad arg list terminator '%s' in coordinator expression '%s'" % (tok, self.string))

        if op == 'match':
            return MatchCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], label=label)
        elif op == 'select':
            return SelectCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], label=label)
        elif op == 'filter':
            return FilterCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'prefix':
            return PrefixFilterCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'suffix':
            return SuffixFilterCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], inverted=args[2], label=label)
        elif op == 'near':
            return NearFilterCoordinator(
                parent=self.parent,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'precedes':
            return PrecedesFilterCoordinator(
                parent=self.parent,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'follows':
            return FollowsFilterCoordinator(
                parent=self.parent,
                patname=args[0],
                feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'count':
            return CountFilterCoordinator(
                parent=self.parent, patname=args[0], feed=args[1], count=args[2], inverted=args[3], label=label)
        elif op == 'snear':
            return SNearFilterCoordinator(
                parent=self.parent,
                left_feed=args[0],
                right_feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'sprecedes':
            return SPrecedesFilterCoordinator(
                parent=self.parent,
                left_feed=args[0],
                right_feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
        elif op == 'sfollows':
            return SFollowsFilterCoordinator(
                parent=self.parent,
                left_feed=args[0],
                right_feed=args[1],
                proximity=args[2],
                inverted=args[3],
                label=label)
#        elif op == 'inter':
#            return IntersectionCoordinator(
#                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
#        elif op == 'union':
#            return UnionCoordinator(
#                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
#        elif op == 'diff':
#            return DiffCoordinator(
#                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
        elif op == 'inter':
            return IntersectionCoordinator(
                parent=self.parent, feeds=args, label=label)
        elif op == 'union':
            return UnionCoordinator(
                parent=self.parent, feeds=args, label=label)
        elif op == 'diff':
            return DiffCoordinator(
                parent=self.parent, feeds=args, label=label)
        elif op == 'contains':
            return ContainCoordinator(
                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
        elif op == 'contained_by':
            return ContainedByCoordinator(
                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
        elif op == 'overlaps':
            return OverlapCoordinator(
                parent=self.parent, left_feed=args[0], right_feed=args[1], label=label)
        # TODO This is not documented, but perhaps the args should be 
        # consistent with connects, which is documented?
        elif op == 'haspath':
            return HasPathFilterCoordinator(
                parent=self.parent,
                left_feed=args[0],
                right_feed=args[1],
                dpath=args[2],
                direction=None,
                label=label)
        elif op == 'connects':
            return ConnectsCoordinator(
                parent=self.parent,
                patname=args[0],
                left_feed=args[1],
                right_feed=args[2],
                label=label)
        # TODO This looks leftover?
        elif op == 'connects_down':
            return ConnectsCoordinator(
                parent=self.parent,
                left_feed=args[0],
                right_feed=args[1],
                dpath=args[2],
                direction="down",
                label=label)
        # The rest are not documented and are probably experimental.
        elif op == 'widen':
            return WidenCoordinator(parent=self.parent, feed=args[0], label=label)
        elif op == 'merge':
            return MergeCoordinator(parent=self.parent, feed=args[0], label=label)
        elif op == 'eval':
            return EvalCoordinator(parent=self.parent, feedname=args[0], label=label)

    def match_extractor_name(self, sel):
        """Is the token interpretable as an extractor name?"""
        return re.match(r'^\w+(?:\.\w+)*$', sel)

    def match_args(self):

        ext = self.toks.pop(0)
        m = self.match_extractor_name(ext)
        if not m:
            raise illegal_extractor_name(ext, self.string)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        # Recurse
        stream = self.seq_stream()

        return (ext, stream)

    def filter_args(self):

        ext = self.toks.pop(0)
        m = self.match_extractor_name(ext)
        if not m:
            raise illegal_extractor_name(ext, self.string)

#        tok = self.toks.pop(0)
#        if tok != ',':
#            raise no_argument_delimiter(tok, self.string)

#        inv = self.toks.pop(0)
#        if inv != '0' and inv != '1':
#            raise invalid_inversion_flag(inv, self.string)

#        invb = (inv == '1')

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        # Recurse
        stream = self.seq_stream()

        invb = False

        if len(self.toks) > 0 and self.toks[0] == ',':
            self.toks.pop(0)
            kw = self.toks.pop(0)
            if kw != 'invert':
                raise invalid_inversion_flag(kw, self.string)
            invb = True

        return ext, stream, invb

    def prox_filter_args(self):

        ext = self.toks.pop(0)
        m = self.match_extractor_name(ext)
        if not m:
            raise illegal_extractor_name(ext, self.string)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        param = self.toks.pop(0)
        try:
            param = int(param)
        except ValueError:
            raise not_non_negative_integer(param, self.string) from None

#        tok = self.toks.pop(0)
#        if tok != ',':
#            raise no_argument_delimiter(tok, self.string)

#        inv = self.toks.pop(0)
#        if inv != '0' and inv != '1':
#            raise invalid_inversion_flag(inv, self.string)

#        invb = inv == '1'

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        # Recurse
        stream = self.seq_stream()

        invb = False

        if len(self.toks) > 0 and self.toks[0] == ',':
            self.toks.pop(0)
            kw = self.toks.pop(0)
            if kw != 'invert':
                raise invalid_inversion_flag(kw, self.string)
            invb = True

        return ext, stream, param, invb

    def proxs_filter_args(self):

        ext = self.seq_stream()

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        param = self.toks.pop(0)
        try:
            param = int(param)
        except ValueError:
            raise not_non_negative_integer(param, self.string) from None

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        inv = self.toks.pop(0)
        if inv != '0' and inv != '1':
            raise invalid_inversion_flag(inv, self.string)

        invb = inv == '1'

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        # Recurse
        stream = self.seq_stream()

        return (ext, stream, param, invb)

    def nary_args(self):

        arg = self.seq_stream()
        args = [arg]

        tok = self.toks.pop(0)
        while tok == ',':
            arg = self.seq_stream()
            args.append(arg)
            tok = self.toks.pop(0)
        if tok != ')':
            raise improper_delimiter(tok, self.string)
        self.toks.insert(0, tok)

        return tuple(args)

    def join_args(self):

        # Recurse
        left = self.seq_stream()

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)

        # Recurse
        right = self.seq_stream()

        return (left, right)

    def haspath_args(self):
        left = self.seq_stream()
        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)
        right = self.seq_stream()
        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)
        #dpath = self.seq_stream()
#        print(self.toks)
        tok = self.toks.pop(0)
        if tok != '"' and tok != "'":
            raise GenericException(msg="No quoted dpath present near '%s'in coordinator expression '%s'" % (tok, self.string))
        endtok = tok
        if endtok not in self.toks:
            raise GenericException(msg="No end quote in dpath present near '%s' in coordinator expression '%s'" % (tok, self.string))
        dpath = []
        tok = self.toks.pop(0)
        while tok != endtok:
            dpath += [tok]
            tok = self.toks.pop(0)
        return (left, right, dpath)

    def connects_args(self):
        ext = self.toks.pop(0)
        m = self.match_extractor_name(ext)
        if not m:
            raise illegal_extractor_name(ext, self.string)

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)
        left = self.seq_stream()  # recurse

        tok = self.toks.pop(0)
        if tok != ',':
            raise no_argument_delimiter(tok, self.string)
        right = self.seq_stream()  # recurse

        return (ext, left, right)

    def eval_args(self):
        ext = self.toks.pop(0)
        return ext,

    def unit_args(self):

        # Single argument. Recurse.
        stream = self.seq_stream()

        return stream,


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
