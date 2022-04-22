import random

from nlpcore.dbfutil import SimpleClass, GenericException

from .transition import Transition, TestTransition, NullTransition

"""
Provides class FAState and subclass FACalloutState.
These are part of the implementation of finite automata used in 
implementing phrase expressions, and parse expressions.
"""

class FAState(SimpleClass):

    DEBUG = False

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        self.transitions = []
        self.count = 0
        self.label = None
        if self.parent:
            self.id = self.parent.counter
            self.parent.counter += 1
            self.parent.states[self.id] = self
#            print "Added new state", self.id, "to FA", self.parent

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

    def transition_to(self, toks, at):
        """Return collection of all the states reachable from this state 
        by one (non-null) transition matching the 'at' token, 
        (followed by any number of null transitions)."""
        # Changing the contract of this method to support selectability of token test matches.
        # Previously it returned a set of state IDs (integers).  Now, it will return a dict
        # mapping the same state IDs to the set of values returned by the match methods of transitions
        # traversed to get to each state in question, either True or the name of the TestTransition.
        result = {}
        for t in self.transitions:
            match = t.matches(toks, at)
            if not match:
                continue
            to_sids = self.parent.null_transitive_closure([t.dest])
            for sid in to_sids:
                try:
                    result[sid].add(match)
                except KeyError:
                    result[sid] = { match }
        return result

    def transit_arcs_to(self, toks, at):
        """Return collection of all the states ((sid, toki) pairs) reachable 
        from this state by one (non-null) transition matching the 'at' token 
        (followed by any number of null transitions)."""
        next_states = set()
        for t in self.transitions:
            for toki in t.arc_matches(toks, at):
                if self.DEBUG:
                    print("At %d (%s), follow %s arc to %d (%s), state %d" % (at, toks[at], t.symbol, toki, toks[toki], t.dest))
                for sid in self.parent.null_transitive_closure((t.dest,)):
                    if self.DEBUG:
                        print("  Adding %d in transitive closure" % sid)
                    next_states.add((sid, toki))
        return next_states

    def null_transition_to(self):
        """Return collection of all the state ids reachable from this state 
        by one or more null transitions."""
        sids = set(t.dest for t in self.transitions if isinstance(t, NullTransition))
        return self.parent.null_transitive_closure(sids)

    def add_transition(self, symbol, ostate=None):
        if ostate:
            new_state = self.parent.get_state(ostate)
        else:
            new_state = FAState(parent=self.parent)
        self.transitions.append(Transition.new(self.parent, self, new_state, symbol))
        return new_state

    def add_test_transition(self, symbol, ostate=None):
        if ostate:
            new_state = self.parent.get_state(ostate)
        else:
            new_state = FAState(parent=self.parent)
        self.transitions.append(TestTransition(fa=self.parent, src=self, dest=new_state, symbol=symbol))
        return new_state

    def add_callout_transition(self, symbol):
        new_state = FACalloutState(parent=self.parent, symbol=symbol)
        self.transitions.append(Transition.new(self.parent, self, new_state))
        fin = new_state.add_transition(None)
        return fin

    def transition_exists(self, symbol, ostate):
        """True if any of our transitions satisfies t.same(symbol, ostate)."""
        existing = [t for t in self.transitions if t.same(symbol, ostate)]
        return len(existing) > 0

    def add_unique_transition(self, symbol, ostate=None):
        """Add a transition to an existing or new state if there is no 
        existing transition for which t.same(symbol, ostate), i.e., 
        whose symbol is symbol and destination is ostate."""
        if ostate:
            new_state = self.parent.get_state(ostate)
        else:
            new_state = FAState(parent=self.parent)
        if not self.transition_exists(symbol, new_state):
            self.transitions.append(Transition.new(self.parent, self, new_state, symbol))
        return new_state

    def incr(self):
        self.count += 1

    def list_transitions(self):
        par = self.parent
        return [ (t.symbol, par.get_state(t.dest)) for t in self.transitions ]

    def clone(self, fa):
        new_state = FAState(parent=fa)
        new_state.count = self.count
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

    def generate_to(self):
        result = []
        num_choices = len(self.transitions)
        if self.parent.is_final(self):
            num_choices += 1
        choice = random.randint(0, num_choices - 1)
        if choice == len(self.transitions):
            return None
        t = self.transitions[choice]
        generation = t.generate_to()
        next_state, emits = generation
        result.extend(emits)
        return (next_state, result)

    def requirements(self):
        req = set()
        for t in self.transitions:
            req |= t.requirements()
        return req

    def __str__(self):
        return str(self.id)  # + " " + super(SimpleClass, self).__str__()


class FACalloutState(FAState):
    """This appears to be used for expression references (@);
    see the code for FiniteAutomaton.atom()."""

    def __init__(self, **args):
        FAState.__init__(self, **args)
        self.reversed = False

    def clone(self, fa):
        new_state = FACalloutState(parent=fa)
        new_state.count = self.count
        new_state.label = self.label
        new_state.symbol = self.symbol
        return new_state

    def dumps(self):
        if self.label:
            label = "%d(%s)" % (self.id, self.label)
        else:
            label = "%d" % self.id
        return label + ':' + self.symbol

    def generate_to(self):
        try:
            fa = self.parent.parent.get_fa(self.symbol)
        except KeyError:
            raise GenericException(msg="Not a phrase expression name: " % self.symbol)
        generation = fa.generate_to()
        if generation is None:
            return None
        final_state, emits = generation
        dest = list(self.null_transition_to())
        choice = random.randint(0, len(dest) - 1)
        return dest[choice], emits

    def requirements(self):
        return super().requirements() | self.parent.manager.requirements(self.symbol)

    def __str__(self):
        return str(self.id) + ":" + self.symbol  # + " " + super(SimpleClass, self).__str__()

