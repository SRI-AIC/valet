import random
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union, TYPE_CHECKING

# See comment in fa.py.
# from ordered_set import OrderedSet as MaybeOrderedSet
MaybeOrderedSet = set

from nlpcore.dbfutil import GenericException
from .transition import Transition, TestTransition, NullTransition
if TYPE_CHECKING:
    from .fa import FiniteAutomaton


"""
Provides class FAState and subclass FACalloutState.
These are part of the implementation of finite automata used in
implementing phrase expressions, and parse expressions.
"""


class FAState:

    __slots__ = ("transitions", "label", "parent", "id", "reversed")

    DEBUG = False

    def __init__(self, parent: 'FiniteAutomaton'):
        self.transitions: List[Transition] = []
        # TODO Used only in commented-out code.
        # self.count = 0
        # TODO Apparently essentially never used.
        self.label = None
        self.parent = parent
        if self.parent:
            self.id = self.parent.counter
            # A method to encapsulate these lines would be nice.
            self.parent.counter += 1
            self.parent.states[self.id] = self
#            print "Added new state", self.id, "to FA", self.parent
        self.reversed = False

#    def transition(self, item):
#        for trans in self.transitions:
#            if trans.matches(item):
#                return self.parent.get_state(trans.dest)
#        return None

#    def transition_to(self, toks, ind):
#        states = set()
#        for t in self.transitions:
#            for state, newind in t.transition_to(toks, ind):
#                states |= (state, newind)
#        return states

    def transition_to(self, toks, at, subst) -> Dict[int, Set[Union[str, bool]]]:
        """Return collection of all the states reachable from this state
        by one (non-null) transition matching the 'at' token,
        (followed by any number of null transitions)."""
        # Changing the contract of this method to support selectability
        # of token test matches.  Previously it returned a set of state IDs
        # (integers).  Now, it will return a dict mapping the same state IDs
        # to the set of values returned by the match methods of transitions
        # traversed to get to each state in question, either True or the name
        # of the TestTransition.
        result = {}
        res_getr = result.get  # avoid dotted lookup within nested loops
        for t in self.transitions:
            match = t.matches(toks, at, subst)
            if not match:
                continue
            to_sids = self.parent.null_transitive_closure([t.dest])
            for sid in to_sids:
                if (matches := res_getr(sid)):
                    matches.add(match)
                else:
                    result[sid] = {match}
        return result

    def transit_arcs_to(self, toks, at, subst) -> Iterable[Tuple[int, int]]:
        """Return collection of all the states ((sid, toki) pairs) reachable
        from this state by one (non-null) arc transition from the 'at' token
        (followed by any number of null transitions)."""
        next_states = MaybeOrderedSet()
        for t in self.transitions:
            for toki in t.arc_matches(toks, at, subst):
                if self.DEBUG:
                    print("At %d (%s), follow %s arc to %d (%s), state %d" % (at, toks[at], t.symbol, toki, toks[toki], t.dest))
                for sid in self.parent.null_transitive_closure((t.dest,)):
                    if self.DEBUG:
                        print("  Adding %d in transitive closure" % sid)
                    next_states.add((sid, toki))
        return next_states

    def null_transition_to(self) -> Set[int]:
        """Return collection of all the state ids reachable from this state
        by one or more null transitions."""
        sids = MaybeOrderedSet(t.dest for t in self.transitions if isinstance(t, NullTransition))
        return self.parent.null_transitive_closure(sids)

    def add_transition(self, symbol, ostate: Optional['FAState'] = None) -> 'FAState':
        """Adds NullTransition if symbol=None, else SymbolTransition.
        Uses ostate as destination if non-null, else creates new FAState;
        returns destination state."""
        if ostate:  # currently this is never passed
            new_state = self.parent.get_state(ostate.id)
        else:
            new_state = FAState(parent=self.parent)
        self.transitions.append(Transition.new(self.parent, self.id, new_state.id, symbol))
        return new_state

    def add_test_transition(self, symbol, ostate: Optional['FAState'] = None) -> 'FAState':
        """Adds TestTransition.
        Uses ostate as destination if non-null, else creates new FAState;
        returns destination state."""
        if ostate:  # currently this is never passed
            new_state = self.parent.get_state(ostate.id)
        else:
            new_state = FAState(parent=self.parent)
        self.transitions.append(TestTransition(fa=self.parent, src=self.id, dest=new_state.id, symbol=symbol))
        return new_state

    def add_callout_transition(self, symbol) -> 'FACalloutState':
        """Adds NullTransition to new FACalloutState destination state
        (symbol is stored in state); returns destination state."""
        new_state = FACalloutState(parent=self.parent, symbol=symbol)
        self.transitions.append(NullTransition(fa=self.parent, src=self.id, dest=new_state.id, symbol=None))
        fin = new_state.add_transition(None)
        return fin

    def transition_exists(self, symbol, ostate) -> bool:
        """True if any of our transitions satisfies t.same(symbol, ostate)."""
        existing = [t for t in self.transitions if t.same(symbol, ostate)]
        return len(existing) > 0

    def add_unique_transition(self, symbol, ostate: Optional['FAState'] = None) -> 'FAState':
        """Add a transition to an existing state or new FAState if there is
        no existing transition for which t.same(symbol, ostate), i.e.,
        whose symbol is symbol and destination is ostate."""
        # Currently symbol is always being passed as None.
        if ostate:  # currently this is always passed
            new_state = self.parent.get_state(ostate.id)
        else:
            new_state = FAState(parent=self.parent)
        if not self.transition_exists(symbol, new_state):
            self.transitions.append(Transition.new(self.parent, self.id, new_state.id, symbol))
        return new_state

    # Never used. See commented-out add_path in fa.py.
    # def incr(self):
    #     self.count += 1

    # Never used.
    # def list_transitions(self):
    #     par = self.parent
    #     return [(t.symbol, par.get_state(t.dest)) for t in self.transitions]

    # Note that this is not a full clone.
    def clone(self, fa):
        new_state = FAState(parent=fa)
        # new_state.count = self.count
        new_state.label = self.label
        return new_state

#     def merge(self, other):
#         # TODO This code looks old, unfinished, and/or broken.
#         # mmap and onsid are set but never used.
#         # build_merge_map is never called.
#         # transitions is probably a list and not a dict.

#         mmap = {}

#         def build_merge_map(s1, s2):
#             mmap[s2.id] = s1.id
#             for item, nsid in s1.transitions.items():
#                 if item in s2.transitions:
#                     onsid = s2.transitions[item]

#         self.count += other.count
#         for item, nsid in self.transitions.items():
#             if item in other.transitions:
#                 onsid = other.transitions[item]

    def dumps(self):
        if self.label:
            return "%d(%s)" % (self.id, self.label)
        else:
            return "%d" % self.id

    def generate_to(self) -> Optional[Tuple[int, List[str]]]:
        result = []
        num_choices = len(self.transitions)
        if self.parent.is_final(self):
            num_choices += 1
        choice = random.randint(0, num_choices - 1)
        if choice == len(self.transitions):
            return None  # no next state
        t = self.transitions[choice]
        next_sid, emits = t.generate_to()
        result.extend(emits)
        return next_sid, result

    def requirements(self, substitutions=None):
        req = set()
        for t in self.transitions:
            req |= t.requirements(substitutions)
        return req

    def __str__(self):
        return f"FAState({self.id})"


class FACalloutState(FAState):
    """This appears to be used for FA rather than token test or literal
    references; see the code for FiniteAutomaton.atom()."""

    __slots__ = ("symbol", "reversed")

    def __init__(self, symbol: str, parent: 'FiniteAutomaton'):
        FAState.__init__(self, parent=parent)
        self.symbol = symbol  # callout rule name
        self.reversed = False

    def clone(self, fa):
        new_state = FACalloutState(symbol=self.symbol, parent=fa)
        # new_state.count = self.count
        new_state.label = self.label
        return new_state

    def dumps(self):
        if self.label:
            label = "%d(%s)" % (self.id, self.label)
        else:
            label = "%d" % self.id
        return label + ':' + self.symbol

    def generate_to(self) -> Optional[Tuple[int, List[str]]]:
        try:
            ext, typ, _ = self.parent.manager.lookup_extractor(self.symbol)
        except Exception:
            raise GenericException(msg="Not a phrase expression name: %s" % self.symbol)
        if typ != 'fa':
            raise GenericException(msg="Not a phrase expression name: %s" % self.symbol)
        generation = ext.generate_to()
        if generation is None:
            return None
        final_state, emits = generation
        dest = list(self.null_transition_to())
        choice = random.randint(0, len(dest) - 1)
        return dest[choice], emits

    def requirements(self, substitutions=None):
        return super().requirements(substitutions) | self.parent.manager.requirements(self.symbol, substitutions)

    def __str__(self):
        return f"FAState({self.id}:{self.symbol})"
