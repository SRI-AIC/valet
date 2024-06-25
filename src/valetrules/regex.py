from abc import ABC, abstractmethod
import functools
import re
from typing import cast, Dict, List, Mapping, Optional, Type, TYPE_CHECKING

from ordered_set import OrderedSet

from nlpcore.dbfutil import SimpleClass, GenericException

from .expression import Expression
from .fa import FiniteAutomaton
from .state import FAState
from .transition import NullTransition
if TYPE_CHECKING:
    from .manager import VRManager


"""
Intermediate representation of token-level regular expressions used in phrase
and parse patterns.
Implementation is via fa.FiniteAutomaton's, created by the compile method.
"""


# Decorator.
def reduce_after(method):
    """reduce() the result of this method call (unless you already reduced it)."""

    def new_method(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if result == self:
            return result
        return result.reduce()

    return new_method


# Rule parsing normally creates Extractors that are stored in a VRManager.
# Regex's (which are not Extractors) are created at rule parse time
# to represent phrase and parse rule regular expressions.
# At rule run time they are converted on demand into FiniteAutomaton's
# (which are Extractors) by VRManager.lookup_own_extractor via Regex.compile.
# Hence Extractor is not a superclass here (at least for now).
# But the set_name and references methods are identical to Extractor's.
#
# The unify and reduce methods, IINM, are not currently used by Valet.
# Apparently they have to do with simplifying regular expressions.
# See scripts/test-regex.py.
# I think they were called by other code that may still exist but
# probably is not being used.
# It looks like there is old code in vrgui.py and gui/stuff.py
# that allowed you to specify multiple dependency paths via the GUI,
# OR (|, altern) them, create a parse rule from them, and reduce()
# the Regex to simplify it.
#
# Note FWIW Regex's are pretty varied and currently rely completely
# on the SimpleClass ctor.
class Regex(SimpleClass, ABC):
    manager: Optional['VRManager']
    fa_class: Type['FiniteAutomaton']
    name: str
    case_insensitive: bool

    def set_name(self, name) -> None:
        self.name = name

    def set_substitutions(self, substitutions: Optional[Mapping[str, str]]) -> None:
        self.substitutions = substitutions

    def references(self) -> OrderedSet[str]:
        return OrderedSet()

    # See comments at caller.
    def compile(self) -> FiniteAutomaton:
        fa = self.fa(self.fa_class, self.manager)
        fa.case_insensitive = self.case_insensitive
        fa.substitutions = self.substitutions
        if hasattr(self, 'name'):
            fa.set_name(self.name)
        # TODO DEBUG: convenient place to test that from_fsm works (it doesn't)
        # regex = from_fsm(fa)
        return fa

    @abstractmethod
    def fa(self, fa_class, manager: 'VRManager') -> FiniteAutomaton:
        raise NotImplementedError()

    @abstractmethod
    def empty(self):
        return False

    # E.g., foo bar baz | foo one baz => foo ( one | bar ) baz.
    @abstractmethod
    def reduce(self):
        raise NotImplementedError()

    # Indirectly called from reduce().
    @abstractmethod
    def unify(self, other):
        raise NotImplementedError()

    @abstractmethod
    def dump(self, ind=""):
        pass


class RegexAtom(Regex):
    symbol: str

    def fa(self, fa_class, manager) -> FiniteAutomaton:
        fa = fa_class(manager=manager, regex=self)
        fa.atom(self.symbol)
        return fa

    def empty(self):
        return False

    def reduce(self):
        return self

    def unify(self, other):
        if not isinstance(other, RegexAtom):
            return other.unify(self)
        elif self.symbol == other.symbol:
            return self
        else:
            return None

    def dump(self, ind=""):
        print("%sAtom(%s)" % (ind, self.symbol))

    def references(self) -> OrderedSet[str]:
        m = re.match(r'[&@]([/\\]?)((\w|\.)+)$', self.symbol)
        if m:
            return OrderedSet((m.group(2),))
        else:
            return OrderedSet()

    def __str__(self):
        return self.symbol

    def __eq__(self, other):
        return isinstance(other, RegexAtom) and self.symbol == other.symbol

    def __hash__(self):
        return hash((RegexAtom, self.symbol))


class RegexConcat(Regex):
    subs: List[Regex]

    def fa(self, fa_class, manager) -> FiniteAutomaton:
        fas = [r.fa(fa_class, manager) for r in self.subs]
        fa = fa_class(manager=manager, regex=self)
        fa.concat(fas)
        return fa

    def empty(self):
        for sub in self.subs:
            if sub.empty():
                return True
        return False

    def unify(self, other):
        if not isinstance(other, RegexConcat):
            return None
        if len(self.subs) != len(other.subs):
            return None
        unifications = [s.unify(o) for s, o in zip(self.subs, other.subs)]
        if None in unifications:
            return None
        return RegexConcat(manager=self.manager, fa_class=self.fa_class, subs=unifications)

    @reduce_after
    def reduce(self):
        # Can't match anything
        if self.empty():
            return nothing

        # no point concatenating one thing (note: concatenating 0 things is
        # entirely valid)
        if len(self.subs) == 1:
            return self.subs[0]

        shared_state = dict(manager=self.manager, fa_class=self.fa_class)

        # Try recursively reducing our internals
        reduced = [m.reduce() for m in self.subs]
        if reduced != self.subs:
            return RegexConcat(subs=reduced, **shared_state)

        # Conc contains "()" (i.e. a mult containing only a pattern containing the
        # empty string)? That can be removed e.g. "a()b" -> "ab"
        for i, sub in enumerate(self.subs):
            if sub == emptystring:
                new = self.subs[:i] + self.subs[i+1:]
                return RegexConcat(subs=new, **shared_state)

        return self

    def zip(self, other, suffix=False) -> 'RegexConcat':
        indices = range(min(len(self.subs), len(other.subs)))
        if suffix:
            indices = [-i - 1 for i in indices]
        subs = []
        for i in indices:
            unification = self.subs[i].unify(other.subs[i])
            if unification is None:
                break
            subs.append(unification)
        if suffix:
            subs = list(reversed(subs))
        return RegexConcat(manager=self.manager, fa_class=self.fa_class, subs=subs)

    def truncate(self, length, beginning=False):
        if beginning:
            newsubs = self.subs[length:]
        else:
            newsubs = self.subs[0:len(self.subs) - length]
        return RegexConcat(manager=self.manager, fa_class=self.fa_class, subs=newsubs)

    def dump(self, ind=""):
        print("%sConcat" % ind)
        for s in self.subs:
            s.dump(ind + "  ")

    def references(self) -> OrderedSet[str]:
        refs = OrderedSet()
        for elt in self.subs:
            refs |= elt.references()
        return refs

    def __str__(self):
        def parenthesize(x):
            if isinstance(x, RegexAltern):
                return "( " + str(x) + " )"
            else:
                return str(x)
        return " ".join([parenthesize(x) for x in self.subs])

    def __eq__(self, other):
        return (isinstance(other, RegexConcat) and
                len(self.subs) == len(other.subs) and
                all(self.subs[i] == other.subs[i] for i in range(len(self.subs))))

    def __hash__(self):
        return hash((RegexConcat, tuple(hash(x) for x in self.subs)))


class RegexAltern(Regex):
    subs: List[Regex]

    def fa(self, fa_class, manager) -> FiniteAutomaton:
        fas = [r.fa(fa_class, manager) for r in self.subs]
        fa = fa_class(manager=manager, regex=self)
        fa.altern(fas)
        return fa

    def empty(self):
        for sub in self.subs:
            if not sub.empty():
                return False
        return True

    # Don't bother
    def unify(self, other):
        return None

    @reduce_after
    def reduce(self):
        # emptiness
        if self.empty():
            return nothing

        shared_state = dict(manager=self.manager, fa_class=self.fa_class)

        # If one of our internal subs is empty, remove it
        newsubs = [s for s in self.subs if not s.empty()]
        if len(newsubs) != len(self.subs):
            return RegexAltern(subs=newsubs, **shared_state)

        # no point alternating among one possibility
        if len(self.subs) == 1:
            return self.subs[0]

        # If at least one alternative is the emptystring, convert into an optional regex
        nonempty = [x for x in self.subs if x != emptystring]
        if len(nonempty) != len(self.subs):
            return RegexOpt(sub=RegexAltern(subs=nonempty, **shared_state), **shared_state)

        # If the present pattern's concs all have a common prefix, split
        # that out. This increases the depth of the object
        # but it is still arguably simpler/ripe for further reduction
        # e.g. "abc|ade" -> a(bc|de)"
        if any(not isinstance(x, RegexConcat) for x in self.subs):
            return self
        self_subs = cast(List[RegexConcat], self.subs)

        common_prefix: RegexConcat = functools.reduce(lambda x, y: x.zip(y), self_subs)
        plen = len(common_prefix.subs)
        if plen > 0:
            new_suffix = [c.truncate(plen, beginning=True) for c in self_subs]
            newsubs = common_prefix.subs + [RegexAltern(subs=new_suffix, **shared_state)]
            return RegexConcat(subs=newsubs, **shared_state)

        common_suffix = functools.reduce(lambda x, y: x.zip(y, True), self_subs)
        slen = len(common_suffix.subs)
        if slen > 0:
            new_prefix = [c.truncate(slen, beginning=False) for c in self_subs]
            newsubs = [RegexAltern(subs=new_prefix, **shared_state)] + common_suffix.subs
            return RegexConcat(subs=newsubs, **shared_state)

        # Try recursively reducing our internals.
        reduced = [c.reduce() for c in self.subs]
        # Unfortunately, frozensets don't preserve order.
        reduced = frozenset(reduced)
        if reduced != frozenset(self.subs):
            return RegexAltern(subs=reduced, **shared_state)

        return self

    def dump(self, ind=""):
        print("%sAltern" % ind)
        for s in self.subs:
            s.dump(ind + "  ")

    def references(self) -> OrderedSet[str]:
        refs = OrderedSet()
        for elt in self.subs:
            refs |= elt.references()
        return refs

    def __str__(self):
        return " | ".join([str(x) for x in self.subs])

    def __eq__(self, other):
        return isinstance(other, RegexAltern) and frozenset(self.subs) == frozenset(other.subs)

    def __hash__(self):
        return hash((RegexAltern, frozenset(hash(x) for x in self.subs)))


class RegexStar(Regex):
    sub: Regex

    def fa(self, fa_class, manager) -> FiniteAutomaton:
        fa = self.sub.fa(fa_class, manager).star()
        fa.regex = self
        return fa

    def empty(self):
        return False

    def unify(self, other):
        if isinstance(other, RegexStar) or isinstance(other, RegexOpt) or isinstance(other, RegexPlus):
            unification = self.sub.unify(other.sub.unify)
            if unification is not None:
                return self
        elif isinstance(other, RegexAtom):
            unification = self.sub.unify(other)
            if unification is not None:
                return self
        return None

    @reduce_after
    def reduce(self):
        # Can't match anything: reduce to nothing
        if self.empty():
            return nothing

        # If we have an empty multiplicand, we can only match it
        # zero times
        if self.sub.empty():
            return emptystring

        reduced = self.sub.reduce()
        if reduced != self.sub:
            return RegexStar(sub=reduced, manager=self.manager, fa_class=self.fa_class)

        return self

    def dump(self, ind=""):
        print("%sStar" % ind)
        self.sub.dump(ind + "  ")

    def references(self) -> OrderedSet[str]:
        return self.sub.references()

    def __str__(self):
        def parenthesize(x):
            if not isinstance(x, RegexAtom):
                return "( " + str(x) + " )"
            else:
                return str(x)
        return parenthesize(self.sub) + " *"

    def __eq__(self, other):
        return isinstance(other, RegexStar) and self.sub == other.sub

    def __hash__(self):
        return hash((RegexStar, hash(self.sub)))


class RegexPlus(Regex):
    sub: Regex

    def fa(self, fa_class, manager):
        fa = self.sub.fa(fa_class, manager).plus()
        fa.regex = self
        return fa

    def empty(self):
        return self.sub.empty()

    def unify(self, other):
        if isinstance(other, RegexStar):
            return other.unify(self)
        elif isinstance(other, RegexPlus):
            unification = self.sub.unify(other.sub)
            if unification is not None:
                return RegexPlus(sub=unification)
        elif isinstance(other, RegexAtom):
            unification = self.sub.unify(other)
            return RegexPlus(sub=unification, manager=self.manager, fa_class=self.fa_class)
        return None

    @reduce_after
    def reduce(self):
        # Can't match anything: reduce to nothing
        if self.empty():
            return nothing

        # If we have an empty multiplicand, we can only match it
        # zero times
        if self.sub.empty():
            return nothing

        reduced = self.sub.reduce()
        if reduced != self.sub:
            return RegexPlus(sub=reduced, manager=self.manager, fa_class=self.fa_class)

        return self

    def dump(self, ind=""):
        print("%sPlus" % ind)
        self.sub.dump(ind + "  ")

    def references(self) -> OrderedSet[str]:
        return self.sub.references()

    def __str__(self):
        def parenthesize(x):
            if not isinstance(x, RegexAtom):
                return "( " + str(x) + " )"
            else:
                return str(x)
        return parenthesize(self.sub) + " +"

    def __eq__(self, other):
        return isinstance(other, RegexPlus) and self.sub == other.sub

    def __hash__(self):
        return hash((RegexPlus, hash(self.sub)))


class RegexOpt(Regex):
    sub: Regex

    def fa(self, fa_class, manager):
        fa = self.sub.fa(fa_class, manager).opt()
        fa.regex = self
        return fa

    def empty(self):
        return False

    def unify(self, other):
        shared_state = dict(manager=self.manager, fa_class=self.fa_class)
        if isinstance(other, RegexStar):
            return other.unify(self)
        elif isinstance(other, RegexOpt):
            unification = self.sub.unify(other.sub)
            if unification is not None:
                return RegexOpt(sub=unification, **shared_state)
        elif isinstance(other, RegexAtom):
            unification = self.sub.unify(other)
            if unification is not None:
                return RegexOpt(sub=unification, **shared_state)
        return None

    @reduce_after
    def reduce(self):
        # Can't match anything: reduce to nothing
        if self.empty():
            return nothing

        # If we have an empty multiplicand, we can only match it
        # zero times
        if self.sub.empty():
            return emptystring

        reduced = self.sub.reduce()
        if reduced != self.sub:
            return RegexOpt(sub=reduced, manager=self.manager, fa_class=self.fa_class)

        return self

    def dump(self, ind=""):
        print("%sOpt" % ind)
        self.sub.dump(ind + "  ")

    def references(self) -> OrderedSet[str]:
        return self.sub.references()

    def __str__(self):
        def parenthesize(x):
            if not isinstance(x, RegexAtom):
                return "( " + str(x) + " )"
            else:
                return str(x)
        return parenthesize(self.sub) + " ?"

    def __eq__(self, other):
        return isinstance(other, RegexOpt) and self.sub == other.sub

    def __hash__(self):
        return hash((RegexOpt, hash(self.sub)))


class RegexExpression(Expression):
    fa_class: Optional[Type[FiniteAutomaton]]
    token_expression: str

    # fa_class is sort of like manager in that some operations don't
    # need it, or only require it to be set, regardless of value.
    def __init__(self, expr: str, manager: Optional['VRManager'], **kwargs):
        super().__init__(expr, manager, **kwargs)
        # Dayne is not sure what the colons were about.
        # self._default('token_expression', r'[&@]?[/\\]?[\w:]+(?:\.[\w:]+)?|\S')
        self._default('token_expression', r'[&@]?[/\\]?[\w]+(?:\.[\w]+)?|\S')
        # Added this to make scripts/test-regex.py run again.
        self._default("fa_class", None)

    def tokenize(self, expr):
        return re.findall(self.token_expression, expr)

    def parse(self) -> Regex:
        self.toks = self.tokenize(self.expr)
        regex = self.altern()
        if len(self.toks) > 0:
            raise GenericException(msg="Extra tokens starting with '%s' in phrase or parse expression '%s'"
                                       % (self.toks, self.expr))
        return regex

    # altern -> concat concat*
    def altern(self) -> Regex:
        altern = []
        regex = self.concat()
        if regex:
            altern.append(regex)
        while len(self.toks) and self.toks[0] == '|':
            self.toks.pop(0)
            altern.append(self.concat())
        if len(altern) == 0:
            raise GenericException(msg="Empty altern in phrase or parse expression '%s'" % self.expr)
        if len(altern) > 1:
            return RegexAltern(subs=altern, manager=self.manager, fa_class=self.fa_class)
        else:
            return altern[0]

    # concat -> operated operated*
    def concat(self) -> Regex:
        concat = []
        regex = self.operated()
        while regex:
            concat.append(regex)
            regex = self.operated()
        if len(concat) == 0:
            raise GenericException(msg="Empty concat in phrase or parse expression '%s'" % self.expr)
        return RegexConcat(subs=concat, manager=self.manager, fa_class=self.fa_class)
        # if len(concat) > 1:
        #     return RegexConcat(subs=concat)
        # else:
        #    return concat[0]

    # operated -> atom | atom '?' | atom '*' | atom '+'
    def operated(self) -> Optional[Regex]:
        regex = self.atom()
        if regex is None:
            return None
        kwargs = dict(sub=regex, manager=self.manager, fa_class=self.fa_class)
        if len(self.toks) == 0:
            return regex
        if self.toks[0] == '?':
            self.toks.pop(0)
            return RegexOpt(**kwargs)
        elif self.toks[0] == '*':
            self.toks.pop(0)
            return RegexStar(**kwargs)
        elif self.toks[0] == '+':
            self.toks.pop(0)
            return RegexPlus(**kwargs)
        else:
            return regex

    # atom -> SYMBOL | '(' altern ')'
    def atom(self) -> Optional[Regex]:
        if len(self.toks) == 0:
            return None
        tok = self.toks[0]
        if tok == '(':
            self.toks.pop(0)
            regex = self.altern()  # recurse
            if len(self.toks) == 0 or self.toks[0] != ')':
                raise GenericException(msg="Unbalanced ')' in phrase or parse expression '%s'" % self.expr)
            self.toks.pop(0)
            return regex
        elif tok == '|' or tok == ')':
            return None
        elif tok == '*' or tok == '?' or tok == '+':
            raise GenericException(msg="Misplaced operator '%s' in phrase or parse expression '%s'" % (tok, self.expr))
        else:
            self.toks.pop(0)
            return RegexAtom(symbol=tok, manager=self.manager, fa_class=self.fa_class)  # bottom out


# TODO: Complete this, if we want it.
# Sasseen: I reorganized a few FA methods to not take "state or id" args so we
# can avoid unnecessary exceptions and states dict lookups in heavily recursive
# and/or loopy code such as in FA. (Also, "explicit is better than implicit".)
# Also modified FA's breadth_first_traversal to return states.
# I made an effort to adjust this function accordingly, but there are some
# typing errors (I also added type decls) which also correspond to runtime
# errors complaining that Regexes don't support |, *, and +.
# I'm not sure if those are just missing for some reason, or if I botched this
# more badly.
# This code can be tested from Regex.compile; see commented-out call there.
def from_fsm(f: FiniteAutomaton):
    """
        Turn the supplied finite state machine into a `lego` object. This is
        accomplished using the Brzozowski algebraic method.
        Adapted from the excellent greenery module.
    """

    # We need a new state not already used
    outside = -1

    # The set of strings that would be accepted by this FSM if you started
    # at state i is represented by the regex R_i.
    # If state i has a sole transition "a" to state j, then we know R_i = a R_j.
    # If state i is final, then the empty string is also accepted by this regex.
    # And so on...

    # From this we can build a set of simultaneous equations in len(f.states)
    # variables. This system is easily solved for all variables, but we only
    # need one: R_a, where a is the starting state.

    # The first thing we need to do is organise the states into order of depth,
    # so that when we perform our back-substitutions, we can start with the
    # last (deepest) state and therefore finish with R_a.
    states: List[FAState] = f.breadth_first_traversal()

    # Our system of equations is represented like so:
    brz: Dict[int, Dict[int, Regex]] = {}
    for a in states:
        brz[a.id] = {}
        for b in states:
            brz[a.id][b.id] = nothing
        brz[a.id][outside] = emptystring if f.is_final(a) else nothing

    # Populate it with some initial data.
    for a in states:
        for t in a.transitions:
            if isinstance(t, NullTransition):
                brz[a.id][t.dest] |= emptystring
            else:
                brz[a.id][t.dest] |= RegexAtom(symbol=t.symbol)

    # Now perform our back-substitution
    for i in reversed(range(len(states))):
        a = states[i]

        # Before the equation for R_a can be substituted into the other
        # equations, we need to resolve the self-transition (if any).
        # e.g.    R_a = 0 R_a |   1 R_b |   2 R_c
        # becomes R_a =         0*1 R_b | 0*2 R_c
        loop = brz[a.id][a.id] * star  # i.e. "0*"
        del brz[a.id][a.id]

        for right in brz[a.id]:
            brz[a.id][right] = (loop + brz[a.id][right]).reduce()

        # Note: even if we're down to our final equation, the above step still
        # needs to be performed before anything is returned.

        # Now we can substitute this equation into all of the previous ones.
        for j in range(i):
            b = states[j]

            # e.g. substituting R_a =  0*1 R_b |      0*2 R_c
            # into              R_b =    3 R_a |        4 R_c | 5 R_d
            # yields            R_b = 30*1 R_b | (30*2|4) R_c | 5 R_d
            univ = brz[b.id][a.id]  # i.e. "3"
            del brz[b.id][a.id]

            for right in brz[a.id]:
                brz[b.id][right] = (brz[b.id][right] | (univ + brz[a.id][right])).reduce()

    return brz[f.initial.id][outside].reduce()


# A regex that matches nothing
nothing = RegexAltern(subs=[])

# A regex that matches the empty string
emptystring = RegexConcat(subs=[])

# An empty loop
star = RegexStar(sub=emptystring)
