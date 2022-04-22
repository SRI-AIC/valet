import re
from os.path import getmtime

from nlpcore.dbfutil import SimpleClass, GenericException
from nlpcore.lexicon import Lexicon
from nlpcore.annotator import Requirement

from .match import FAMatch, FAArcMatch
from .state import FAState, FACalloutState
from .transition import NullTransition

"""
Provides FiniteAutomaton class and subclasses such as ArcFiniteAutomaton.
These implement finite automata used in implementing 
token tests, phrase expressions, and parse expressions.

A finite automaton consists of an interconnected set of states and 
# transitions that can be used to recognize a matching sequence of tokens.
# Key FiniteAutomaton recognition operations are match, search, and scan; 
# see VRManager for an overview of what those mean.
"""

# AFAICT the bounds args to methods like scan, search, and match 
# are never passed as anything but None, and are never checked 
# except by Sequence{Start,End}FiniteAutomaton. 
# The bounds args are intended to support matching phrase expressions 
# with @START/@END against token SUBsequences via coordinators. 
# TODO We'd need to start passing bounds args from coordinators, 
# and pass them along through intermediate methods. 
# Currently some of those methods don't even accept bounds args.
class FiniteAutomaton(SimpleClass):

    counter = 0  # used in assigning numeric IDs to states of the FA

    # Instance variables:
    # name -- Typically named after LHS of pattern.
    # manager -- FAManager we belong to; needed to find other FAs we depend on.
    # states -- Map from state id (an integer [TODO or a string representing an integer?]) to state.
    # initial -- Initial state.
    # final -- Map from state to whether it's final.

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        # Max number tokens from the starting point we will consider
        # when matching. Presumably defends against inadvertently incorrect
        # or perhaps overly expensive patterns, or unusually long 
        # token sequences.
        self._default('max_match', 300)
        self._default('case_insensitive', False)
        self.states = {}
        self.initial = FAState(parent=self)
        self.final = {self.initial.id: True}  # why?

    def get_state(self, state):
        try:
            sid = state.id
        except:
            sid = state
        return self.states[sid]

    def make_final(self, state, final=True):
        try:     # State
            self.final[state.id] = final
        except:  # State ID
            self.final[state] = final

    def is_final(self, state):
        try:
            sid = state.id
        except:
            sid = state
        return sid in self.final and self.final[sid]

    def get_final_states(self):
        return [self.states[s] for s,f in self.final.items() if f]

    # The methods atom, concat, altern, star/plus/opt are typically used
    # to initialize a newly created FA.
    # They're called from, eg, the fa() methods of regex.Regex's.

    def atom(self, symbol):
        """
        If the symbol starts with a reference symbol ('&' or '@'):
            add a test transition if a test of the indicated name exists
            else add a callout transition
        Else a literal transition
        """
        m = re.match(r'[&@]([/\\]?)((\w|\.)+)$', symbol)
        if m:
            arc_dir = m.group(1)
            name = m.group(2)
            have_test = self.manager.test_defined(name)
            if have_test:
                final = self.initial.add_test_transition(symbol[1:])
            elif len(arc_dir) > 0:
                raise GenericException(msg="Direction '%s' specified on missing test (%s)" % (arc_dir, name))
            else:
                final = self.initial.add_callout_transition(symbol[1:])
        else:
            final = self.initial.add_transition(symbol)
        self.make_final(self.initial, False)
        self.make_final(final)
        return self

    def atom_old(self, symbol):
        """Make the FA represent a token test reference (symbol = "&ttname"),
        expression reference (symbol = "@exname"), or string literal (symbol =
        anything else)."""
        if re.match(r'&[/\\]?(\w|\.)+$', symbol):
            final = self.initial.add_test_transition(symbol[1:])
        elif re.match(r'@(\w|\.)+$', symbol):
            final = self.initial.add_callout_transition(symbol[1:])
        else:
            final = self.initial.add_transition(symbol)
        self.make_final(self.initial, False)
        self.make_final(final)
        return self

    def concat(self, fas):
        """Appears to roughly copy the other FAs and assemble them into
        a larger one, connected by null transitions."""
        for fa in fas:
            init = fa.initial
            final = self.get_final_states()
            statemap = self.eat(fa)
            init = statemap[init.id]
            for state in final:
                state.add_unique_transition(None, init)
                self.make_final(state, False)
            for state in fa.get_final_states():
                self.make_final(statemap[state.id])
        return self

    def altern(self, fas):
        """Appears to roughly copy the other FAs and assemble them into
        a larger one, connected by null transitions."""
        final = self.get_final_states()
        for state in final:
            self.make_final(state, False)
        for fa in fas:
            init = fa.initial
            statemap = self.eat(fa)
            init = statemap[init.id]
            for state in final:
                state.add_unique_transition(None, init)
            for state in fa.get_final_states():
                self.make_final(statemap[state.id])
        return self

    def star(self):
        """Implemented as plus() followed by opt()."""
        return self.plus().opt()

    def plus(self):
        """Add null transitions from all final states back to initial state
        (expresses arbitrary number of repetitions)."""
        init = self.initial
        final = self.get_final_states()
        for state in final:
            state.add_unique_transition(None, init)
        return self

    def opt(self):
        """Add null transitions from initial state to all final states
        (expresses optionality)."""
        init = self.initial
        final = self.get_final_states()
        for state in final:
            init.add_unique_transition(None, state)
        return self

    def eat(self, fa):
        """Appears to roughly clone the state map of the other FA,
        making the cloned states and transitions children of "self"."""
        statemap = dict((s.id, s.clone(self))
                        for s in fa.states.values())
        for sid, newstate in statemap.items():
            state = fa.get_state(sid)
            for trans in state.transitions:
                newtrans = trans.clone()
                newtrans.src = newstate.id
                newtrans.dest = statemap[trans.dest].id
                newtrans.fa = self
                newstate.transitions.append(newtrans)
        return statemap

    # Experimenting with not cloning, which changes the IDs, just re-parenting
    # the states and transitions.
    # Seems to work fine.
    # TODO? Perhaps use this instead if it makes sense, or get rid of it
    # if it doesn't?
    def eatNew(self, fa):
        """Re-parent the states and transitions of fa from fa to self."""
        statemap = dict((s.id, s)
                        for s in fa.states.values())
        for sid, state in statemap.items():
            state.parent = self
            self.states[sid] = state
            for trans in state.transitions:
                trans.fa = self
        return statemap

#     def add_path(self, items):
#         state = self.initial
#         for item in items:
#             next_state = state.transition(item)
#             if not next_state:
#                 next_state = state.add_unique_transition(item)
#                 next_state.label = item
#             state = next_state
#             state.incr()

    def dump(self):
        """
        Print a human-readable representation of the FA showing states 
        and transitions.
        > indicates an initial state and @ a final state.
        """
        print(self.dumps())

    def dumps(self):
        """
        Print a human-readable representation of the FA showing states 
        and transitions.
        > indicates an initial state and @ a final state.
        """

        # used to track which transitions have been visited
        visited = {}

        def do_dumps(state):
            """Print name of state, preceded by > for an initial state
            or @ for a final state, followed by the state's transitions,
            and then recurse into the transitions' destination states."""
            visited[state.id] = True
            s = []
            if state is self.initial:
                s.append(">")
            if self.is_final(state):
                s.append("@")
            s.append(state.dumps())
            s.append("\n")
            for trans in state.transitions:
                s.append(trans.dumps("  "))
                s.append("\n")
            for trans in state.transitions:
                if trans.dest not in visited:
                    s.extend(do_dumps(self.get_state(trans.dest)))
            return s

        return "".join(do_dumps(self.initial))

    def loopy(self):
        """Methods that check for loops, used in debugging patterns."""

        visited = {}

        def loopy_at_state(state):
            if state.id in visited:
                return True
            visited[state.id] = True
            for trans in state.transitions:
                next_state = self.get_state(trans.dest)
                if loopy_at_state(next_state):
                    return True
            return False

        return loopy_at_state(self.initial)

    def clone(self):
        fa = FiniteAutomaton(manager=self.manager)
        for id, state in self.states.items():
            fa.states[id] = state.clone(fa)
            if state == self.initial:
                fa.initial = fa.states[id]
        return fa

    def reverse(self):
        """Return a new FA that matches the same sequences as the current one,
        but in reversed token order."""

        fa = self.clone()

        # Reverse all transitions
        for sid, state in self.states.items():

            # Erase finality for now.  We'll designate a final state below.
            fa.make_final(sid, False)

            # Make sure all callout states are also reversed
            if isinstance(state, FACalloutState):
                fa.manager.get_reversed_fa(state.symbol)
                fa.states[sid].reversed = not state.reversed

            # dest = fa.states[sid]
            for trans in state.transitions:
                newtrans = trans.reverse()
                newtrans.fa = fa
                src = fa.states[newtrans.src]
                src.transitions.append(newtrans)

        # Create a new start state with null trans to previously final states
        fa.initial = FAState(parent=fa)
        for sid in (sid for sid in self.final.keys() if self.final[sid]):
            fa.initial.transitions.append(NullTransition(fa=fa, src=fa.initial.id, dest=sid))

        # Make the previously initial state final
        fa.make_final(self.initial.id, True)

        return fa

    # Regarding all the null transitions, Dayne said that there are
    # so many of them because they're convenient to enable building up
    # larger FAs out of smaller independent constituents in a
    # straightforward way.
    # For example, see the atom, concat, altern, star/plus/opt methods
    # of this class.
    def null_transitive_closure(self, sids):
        """ Gives the transitive closure, under null transitions only, 
        of the collection of state ids."""
        sids = set(sids)
        # First follow all single null transitions from the states.
        newsids = set(t.dest for s in sids for t in self.states[s].transitions
                        if isinstance(t, NullTransition) and t.dest not in sids)
        # Now quasi-recursively follow all null transitions, except ones 
        # from callout states, since we've not descended into those yet.
        while len(newsids) > 0:
            sids |= newsids
            newstates = (self.states[s] for s in newsids)
            newsids = set(t.dest for s in newstates for t in s.transitions
                            if isinstance(t, NullTransition) and t.dest not in sids
                            and not isinstance(s, FACalloutState))
        return sids

    def match_from_state(self, toks, sid, start, end, bounds=None):
        """Generator matching this FA against tokens, starting at specified 
        start token, starting from specified state, potentially generating 
        multiple matches if there are multiple ways to match."""
        ## print(" In %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

        def match(at, state):
            """Generator matching this FA against tokens 
            (having started at start token specified by match_from_state), 
            continuing from specified state and at token, potentially 
            generating multiple matches if there are multiple ways to match.
            Generates match object with end value showing how far in tokens
            we could match (if we could match up to a final state)."""

            ## print("  In %s.match_from_state.match(at=%d, state=%s)" % (self.name, at, state))
            if at > end or at - start > self.max_match:
                return
            # just for debug; at can = end when we recurse one time too many
            tok = toks[at] if at < end else None

            if isinstance(state, FACalloutState):
                # FACalloutState is used for references from one phrase 
                # expression to another (using @).
                # "Descend" into the FA for that and match against it.

                # The "symbol" attribute exists mostly to allow us to get the FA here.
                ## print("   Descending into %s at token %d '%s'" % (state, at, tok))
                assert not state.reversed
                #if state.reversed:
                    # We're scanning backward, and need an inverted FA. (We don't do that anymore.)
                    #fa = self.manager.get_reversed_fa(state.symbol)
                #fa = self.manager.get_fa(state.symbol)

                fa, type_ = self.manager.lookup_extractor(state.symbol)
#                if fa is None:
#                    raise GenericException(msg="Could not resolve '@%s'; is that really the name of a phrase expression pattern? Note that phrase expressions cannot reference parse expressions (or vice-versa)." % state.symbol)
                if fa is None:
                    raise GenericException(msg="Could not resolve reference to '%s'; is that really the name of a pattern?" % state.symbol)
                elif type_ == "test":
                    # Code should have taken the non-callout branch in this case.
                    # raise GenericException(msg="Code should not get here for a token test (%s)" % state.symbol)
                    # TODO? Actually, the FA-building code does not yet 
                    # drill down into sub-managers when checking whether 
                    # a reference is to a token test or to a "callout" 
                    # phrase or parse expression, so references like 
                    # &chars.dash get compiled with TestTransitions to 
                    # FAStates, not callout Transitions to FACalloutStates.
                    # See FA.atom and VRManager.test_defined.
                    pass
                elif type_ != "fa" and type_ != "coord":
                    raise GenericException(msg="'%s' reference in phrase expression must refer to another phrase expression, a token test expression, or a coordinator expression, but it refers to a %s expression." % (state.symbol, self.anager.extractor_type_to_long_name(type_)))

                ## matched1 = False
                for sm in self.manager.matches(state.symbol, toks, at, end, bounds):  # quasi-recurse into the referenced FA (or other extractor)
                #for sm in fa.matches(toks, at, end, bounds):
                    ## matched1 = True
                    sm.name = state.symbol
                    if self.is_final(state):
                        # We never see this. Probably FAs are set up 
                        # such that callout states are never final.
                        print("  ## Matched", state.symbol, "with submatch", sm)
                        yield FAMatch(seq=toks, begin=start, end=sm.end, submatches=[sm], name=self.name)

                    # Regardless of whether state is final and we yielded 
                    # a match, might still be able to continue matching 
                    # from here and get to another final state.
                    dest = state.null_transition_to()
                    ## if len(dest) == 0:
                    ##     print("   No null transitions from state %d available to continue matching" % state.id)
                    # print("Trying null transitions from", str(state.id), "to", dest)
                    for sid in dest:
                        ## print("   Trying null transition from state %d to %d" % (state.id, sid))
                        ## matched2 = False
                        deststate = self.states[sid]
                        for m in match(sm.end, deststate):  # recurse from where last match left off
                            # The callout FA's match (that took us from 'at' 
                            # to sm.end) is a submatch of this FA's match.
                            ## print("   Adding submatch %s to %s" % (sm, m))
                            m.add_submatch(sm)
                            # print("Back successfully from", deststate)
                            yield m
                        ## if not matched2:
                        ##     print("   Unable to continue from state %d after matching callout %s" % (deststate.id, sm.name))
                ## if not matched1:
                ##     print("   Descending into %s at token %d '%s' failed to match" % (state, at, tok))
            else:
                # Regular state, try to transition, consuming one token.
                # First try to consume a token and recurse as long as we can do so.
                if at < end:
                    dest = state.transition_to(toks, at)
                    ## if len(dest) == 0:
                    ##     print("   Unable to consume token %d '%s' from state %d" % (at, tok, state.id))
                    # if len(dest) > 0:
                    #     print("Transitioning from state", str(state.id), "to", dest, "on token=" + tok)
                    # dest is now a dict mapping state IDs to all transition.match returns that got us to them
                    for sid, transition_matches in dest.items():
                        # TODO? We end up throwing these submatches away
                        # if the recursion below does not succeed.
                        submatches = [ FAMatch(seq=toks, begin=at, end=at+1, name=tm)
                                       for tm in transition_matches if isinstance(tm, str) ]
                        ## print("   Transitioning from state %d to %d on token %d '%s' with potential submatches %s" % (state.id, sid, at, tok, [str(sm) for sm in submatches]))
                        ## matched = False
                        deststate = self.states[sid]
                        for m in match(at+1, deststate):  # recurse
                            ## matched = True
                            # The token test matches (that took us from 'at' 
                            # to at+1) are submatches of this FA's match.
                            for sm in submatches:
                                ## print("   Adding submatch %s to %s" % (sm, m))
                                m.add_submatch(sm)
                            yield m
                        ## if not matched:
                        ##     print("   Unable to continue matching from %d; dropping potential submatches" % deststate.id)
                # else:  # not at < end
                #     pass  # working on what I want to print here

                # We were not able to continue further matching from
                # destination states. Is the current state final?
                if self.is_final(state):
                    m = FAMatch(seq=toks, begin=start, end=at, name=self.name)
                    ## print("   # Yielding %s from final state %s with current token %d '%s' (one past end of match)" % (m, state, at, tok))
                    yield m
                # else:
                #     pass  # working on what I want to print here
            ## print("  Leaving %s.match_from_state.match(at=%d, state=%s)" % (self.name, at, state))
        # end nested def match(at, state)

        # matched = False
        state = self.states[sid]
        for m in match(start, state):
            # matched = True
            yield m
        # if not matched:
        #     print("No match from sid=%d start=%s end=%s" % (sid, start, end))
        ## print(" Leaving %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

    def matches(self, toks, start=0, end=None, bounds=None):
        """Generator matching this FA against tokens, starting only 
        at specified start token, starting from initial state,
        potentially generating multiple matches if there are multiple ways
        to match. Drops zero-length matches."""
        if end is None:
            end = len(toks)
        states = self.null_transitive_closure([self.initial.id])
        ## print("In %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))
        for sid in states:
            for m in self.match_from_state(toks, sid, start, end, bounds):
                # m.end == m.start (== start) can happen for zero-length 
                # matches from *, ?, and presumably @START/@END.
                # Not sure about @ROOT.
                if m.end != start:
                    ## print("%s.matches(tokens, start=%d) found match %s from state %d" % (self.name, start, m, sid))
                    yield m
                ## else:
                ##    print("DEBUG: name=%s m.end=%d == start=%d" % (self.name, m.end, start))
        ## print("Leaving %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))

    def match(self, toks, start=0, end=None, bounds=None):
        """Match this FA against tokens, starting only at start token,
        starting from initial state,
        returning longest match if there are multiple ways to match,
        None if there are no matches."""
        # print("In", self.name + ".match(tokens, start=" + str(start) + ", end=" + str(end) + ")")
        # As noted in matches(), end == begin can happen for zero-length 
        # matches. 
        # end < start can probably happen if the present method is called 
        # on ArcFiniteAutomaton, which overrides matches() but not match().
        # However, the present method is not called on ArcFiniteAutomaton 
        # by any of our typical code paths.
        matches = [m for m in self.matches(toks, start, end, bounds)
                   if m.end >= m.begin]

        try:
            # matches = list(matches)  # debug
            mx = max(matches, key=lambda m: m.end)
            # print("Returning longest match for self:", self.name + ":" + str(mx.begin) + ":" + str(mx.end))
            return mx
        except ValueError:
            return None  # matches was empty

    def search(self, toks, start=0, end=None, bounds=None):
        """Match this FA against tokens, starting at every starting point
        from start on, returning the longest match found from the first 
        starting point where there is a match, or None."""
        # print("In", self.name + ".search(tokens, start=" + str(start) + ", end=" + str(end) + ")")
        if end is None:
            end = len(toks)
        while start < end:
            m = self.match(toks, start, end, bounds)
            if m:
                return m
            start += 1
        return None

    # Note FWIW that the scan, search, and match methods of FiniteAutomaton 
    # are somewhat different from the same-named methods of VRManager, 
    # at least on the surface.
    # For example, VRManager.scan does not start searching for the next match 
    # where the last match stopped, as is done here.
    # And whereas here scan calls search which calls match, there scan, 
    # search, and match all call a method _scan. 
    # Coordinators were only recently given scan methods, and those are 
    # at least superficially different as well.
    # Token tests have scan and matchES methods.
    def scan(self, toks, start=0, end=None, bounds=None):
        """
        Generate matches falling within specified start/end range, but choosing
        only the longest match at any starting point, and starting search 
        for the next match where the last one stopped.
        """
        # print("In", self.name + ".scan(tokens=" + str(toks.tokens) + ", start=" + str(start) + " end=" + str(end) + ")")
        # self.dump()
        m = self.search(toks, start, end, bounds)
        while m:
            yield m
            start = m.end  # start next search where last one stopped
            # Trying to fix matching of START in test_phrase.py, 
            # but didn't work as hoped. Still working on that issue.
            # start = min(start+1, m.end)  # start next search where last one stopped
            m = self.search(toks, start, end, bounds)

    def generate_to(self):
        state = self.initial
        result = []
        trans = state.generate_to()
        while trans is not None:
            next_state, emits = trans
            result.extend(emits)
            state = self.states[next_state]
            trans = state.generate_to()
        return (state, result)

    def generate(self):
        state, emits = self.generate_to()
        return emits

    def breadth_first_traversal(self):
        states = [self.initial]
        i = 0
        while i < len(states):
            current = states[i]
            for t in current.transitions:
                if t.dest not in states:
                    states.append(t.dest)
            i += 1
        return states

    def traverse(self):
        states = [self.initial]
        i = 0
        while i < len(states):
            current = self.get_state(states[i])
            yield current
            for t in current.transitions:
                if t.dest not in states:
                    states.append(t.dest)
            i += 1

    def requirements(self):
        req = set()
        for s in self.traverse():
            req |= s.requirements()
        return req

    def __str__(self):
        return object.__str__(self) + "[name=" + (self.name if hasattr(self, "name") else "None") + "]"


class ArcFiniteAutomaton(FiniteAutomaton):

    def match_from_state(self, toks, sid, start, end, bounds=None):
        """Generator matching this FA over the dependency graph, starting
        at specified start token, starting from specified state,
        potentially generating multiple matches if there are multiple ways
        to match."""
        ## print(" In %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

        def match(at, state, visited=set()):
            """Generator matching this FA against dependency graph 
            (having started at start token specified by match_from_state), 
            continuing from specified state and at token, potentially 
            generating multiple matches if there are multiple ways to match.
            Generates match object with end value showing how far in tokens
            we could match (if we could match up to a final state)."""

            ## print("  In %s.match_from_state.match(at=%d, state=%s)" % (self.name, at, state))
            if at > end or at - start > self.max_match:
                return
            # just for debug; not sure if at can = end in arc FAs
            # tok = toks[at] if at < end else None
            # print("In FAArcMatch.match, tok=%s" % tok)

            # Disallow repeat visits to a state (from a given 'at' value).
            # (Not needed for regular FA since can't go backward in those.)
            if (state.id, at) in visited:
                return
            visited |= set([(state.id, at)])

            if isinstance(state, FACalloutState):
                # FACalloutState is used for references from one parse 
                # expression to another (using @).
                # "Descend" into the FA for that and match against it.

                # The "symbol" exists mostly to allow us to get it here.
                ## print("   Descending into %s at token %d '%s'" % (state, at, tok))
                fa, type_ = self.manager.lookup_extractor(state.symbol)
                if fa is None:
                    raise GenericException(msg="Could not resolve reference to '%s'; is that really the name of a pattern?" % state.symbol)
                elif type_ == "test":
                    # Code should have taken the non-callout branch in this case.
                    # raise GenericException(msg="Code should not get here for a token test (%s)" % state.symbol)
                    # See comment in FA code.
                    pass
                elif type_ != "dep_fa":
                    raise GenericException(msg="'%s' reference in parse expression must refer to another parse expression or to a token test expression, but it refers to a %s expression." % (state.symbol, self.manager.extractor_type_to_long_name(type_)))

                for sm in self.manager.matches(state.symbol, toks, at, end, bounds):  # quasi-recurse into referenced arc FA (or token test)
                    sm.name = state.symbol
                    if self.is_final(state):
                        # I think we never see this? Probably ArcFAs are 
                        # set up such that callout states are never final.
                        # The corresponding spot in FA doesn't happen.
                        print("  ## ArcFA matched", state.symbol, "with submatch", sm)
                        yield FAArcMatch(seq=toks, begin=start, end=sm.end, submatches=[sm], name=self.name)

                    # This check seems incorrect. There is no clearly 
                    # defined purpose for it; it is inconsistent with 
                    # the non-callout branch of the code; and it leads 
                    # to undesired behavior as illustrated in tests.
                    # if sm.end < at:
                    #     # print("  ## sm.end == %d < at == %d, not continuing matching from submatch end" % (sm.end, at))
                    #     continue

                    # As in FA, try to continue matching from sm.end.
                    dest = state.null_transition_to()
                    for sid in dest:
                        deststate = self.states[sid]
                        for m in match(sm.end, deststate, visited):
                            # print("  ## Adding arc submatch %s to %s" % (sm, m))
                            m.add_submatch(sm)
                            yield m
            else:
                # Regular state, try to transition, consuming one token (arc label).
                # First try to consume a token and recurse as long as we can do so.
                if at < end:
                    next_states = state.transit_arcs_to(toks, at)
                    for sid,toki in next_states:
                        deststate = self.states[sid]
                        for m in match(toki, deststate, visited):  # recurse
                            # Unlike for regular FAs, we don't record token 
                            # test matches of the labels as submatches of m.
                            yield m
                # else:  # not at < end
                #     pass  # working on what I want to print here

                # We were not able to continue further matching from
                # destination states. Is the current state final?
                if self.is_final(state):
                    # print "Reached final state ", str(state.id)
                    m = FAArcMatch(seq=toks, begin=start, end=at, name=self.name)
                    yield m

        state = self.states[sid]
        for m in match(start, state):
            yield m

    # RVS: I've seen enough anomalies to believe that ArcFA almost certainly 
    # needs its own version of this method, which it previously was inheriting 
    # from FA. No functional changes made so far, though.
    # Any reference to "end" should be looked at with suspicion, 
    # since the convention is different from FAMatch's.
    def matches(self, toks, start=0, end=None, bounds=None):
        """Generator matching this FA against tokens, starting only 
        at specified start token, starting from initial state,
        potentially generating multiple matches if there are multiple ways
        to match. Drops zero-length matches."""
        if end is None:
            end = len(toks)
        states = self.null_transitive_closure([self.initial.id])
        ## print("In %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))
        for sid in states:
            for m in self.match_from_state(toks, sid, start, end, bounds):
                # m.end == m.start (== start) can happen for zero-length 
                # matches from *, ?, and presumably @START/@END.
                # TODO? Not clear whether there are bugs here.
                # Possibly not, since ArcFA matches generally encompass at 
                # least one edge, so two tokens.
                # Not sure about @ROOT, though.
                if m.end != start:
                    ## print("%s.matches(tokens, start=%d) found match %s from state %d" % (self.name, start, m, sid))
                    yield m
                ## else:
                ##    print("DEBUG: name=%s m.end=%d == start=%d" % (self.name, m.end, start))
        ## print("Leaving %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))

    def scan(self, toks, start=0, end=None, bounds=None):
        """
        Generate all matches falling within specified start/end range.
        Note that this method behaves differently from the corresponding
        FiniteAutomaton method in an important way.  FA.scan() consumes
        tokens sequentially, jumping over any tokens implicated in
        intermediate matches.  This is problematic for an extractor that
        crawls a graph that can jump back, forth, and over intermediate
        tokens.  In particular, adopting the same semantics here can lead to
        unpredictable behavior, with matches depending on the order in which
        dependencies are listed in internal data structures.
        For example, if a noun headword has multiple 'nmod' dependencies and
        the first in the list yields a successful match, adopting FA.scan()
        semantics will fail to yield matches that might follow by crawling
        subsequent 'nmod' dependencies, even if those matches might be
        preferable for downstream uses.
        Consequently, this method extracts more exhaustively than FA.scan().
        """
        # print("In", self.name + ".scan(tokens=" + str(toks.tokens) + ", start=" + str(start) + " end=" + str(end) + ")")
        # self.dump()

        if end is None:
            end = len(toks)
        while start < end:
            for m in self.matches(toks, start, end, bounds):
                # When the scan method was added, we initially required
                # m.end >= m.begin here in order to yield a match. 
                # Dayne wrote that that
                # "breaks code that was working previously.
                #  We shouldn't be doing this kind of check at this level. 
                #  Scan is invoked in contexts and under assumptions 
                #  that are hard to predict."
                # I believe we now tend to yield one match in each direction,
                # ie one with m.end > m.begin and one with m.end < m.begin
                # (if m.end != m.begin).
                # Downstream code may need to be aware of that and perhaps
                # take action at that point if desired.
                yield m
            start += 1

    def requirements(self):
        req = super().requirements()
        req.add(Requirement.DEPPARSE)
        return req


# Note FWIW that these next three classes are used only for phrase expressions 
# (see START/END/ROOT in VRManager).
# TODO Would it make any sense to have versions of them for parse expressions?
# 
# Note that the matches methods are used for "callouts" from one phrase 
# (or parse) expression to another, which is the primary use of these 
# classes (or at least of the first two), rather than being called 
# at top level themselves.
#
# TODO For completeness, might want to give these two (or three) classes 
# scan methods; otherwise they inherit parent class methods.
# That may be why they didn't work as expected at top level in unit tests, 
# now commented out.


# There are two possible valid semantics for # START/END extractors. 
# In one, they only match at the the tseq start/end, ie 0 and len(toks).
# In the other, they respect the bounds of the matches that they're 
# supposed to be matching in. 
# (See test_start_end in test_coordinator.py.)
# 
# The code has been slightly mixed up about this. 
# The bounds parameter to several methods was intended for implementing 
# the second semantics, but so far it has never been passed to originate, 
# only passed along from one reciever to another, so it has only ever 
# had the default value (None) given by the original receiver.
# I.e., the second semantics has never been implemented. 
# Some of the groundwork had been laid, but the work had not been completed, 
# and so the groundwork may or may not have taken the ideal form.
# (I have some thoughts about this that I'm not putting down here.)
#
# The first semantics had been essentially implemented, but there was 
# a bug in SeqEndFA that showed up when we started adding end arguments 
# to VRManager and coordinator methods, and passing them from coordinators, 
# where SeqEndFA was looking at the end arg instead of len(toks).
# (There was a similar but opposite bug in FA.search as well.)
#
# The bottom line is that we are now consciously choosing the first semantics 
# for START/END. 
# We have use cases on some projects where we need that semantics.
# The second semantics is also of interest and potentially useful, and we 
# may choose to complete an implementation of that later, but we will use 
# different extractor names.
# (I'm going to call them SSTART/SEND for now, although Dayne would prefer 
# longer and more descriptive names.)
# That means we don't need to deal with the bounds args for the time being; 
# we can just leave the code as it is (after fixing the first semantics bugs).


class SequenceStartFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in START phrase extractor."""

    def matches(self, toks, start=0, end=None, bounds=None):
        if bounds is not None:
            if start == bounds[0]:  # bounds start
                yield FAMatch(seq=toks, begin=start, end=start, name="START")
        else:
            if start == 0:
                m = FAMatch(seq=toks, begin=start, end=start, name="START")
                ## print("    # Yielding %s" % m)
                yield m


class SequenceEndFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in END phrase extractor."""

    def matches(self, toks, start=0, end=None, bounds=None):
        if bounds is not None:
            if start == bounds[1]:  # bounds end
                yield FAMatch(seq=toks, begin=start, end=start, name="END")
        else:
            if start == len(toks):
                m = FAMatch(seq=toks, begin=start, end=start, name="END")
                ## print("    # Yielding %s" % m)
                yield m


# The point of this is to identify the root verb in the parse tree 
# (or whatever the root word is if the tseq is a sentence fragment).
# Note that somewhat counterintuitively, this is an FA, not an ArcFA.
# TODO? Do we want a scan method for this?
class ParseRootFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in ROOT phrase extractor.
    We're changing the semantics of this so that it always matches a sentences head words."""

    def matches(self, toks, start=0, end=None, bounds=None):
        if end is None:
            end = len(toks)
        # Force NLP, so we know we have syntactic annotation
        toks._maybe_nlp()
        matches = False
        for at in range(start, end):
            deps = toks.get_up_dependencies(at)
            if any(index == -1 for index, _ in deps):
                matches = True
            else:
                if matches:
                    yield FAMatch(seq=toks, begin=start, end=at, name="ROOT")
                return

    def requirements(self):
        return set([Requirement.DEPPARSE])

#    def matches(self, toks, start=0, end=None, bounds=None):
#        yield FARootMatch(seq=toks)


class LexiconMatcher(FiniteAutomaton):

    LEXICONS = {}

    @classmethod
    def load_lexicon(cls, lexicon_file, case_insensitive, is_csv, target_column, manager):
        key = (lexicon_file, case_insensitive, is_csv, target_column)
        file_mtime = getmtime(lexicon_file)
        if key in cls.LEXICONS:
            lexicon, cache_mtime = cls.LEXICONS[key]
            if cache_mtime == file_mtime:
                return lexicon
        if manager.verbose:
            print("Loading lexicon: %s" % lexicon_file)
        lexicon = Lexicon(case_insensitive)
        if is_csv:
            lexicon.load_from_csv(lexicon_file, target_column)
        else:
            lexicon.load_from_text(lexicon_file)
        cls.LEXICONS[key] = (lexicon, file_mtime)
        return lexicon

    def __init__(self, lexicon_file, case_insensitive, is_csv, target_column, manager):
        # deliberately not calling superclass init?
        self.manager = manager
        self.lexicon = self.load_lexicon(lexicon_file, case_insensitive, is_csv, target_column, manager)

    def matches(self, toks, start=0, end=None, bounds=None):
        for to, payload in self.lexicon.matches(toks, start, end):
            yield FAMatch(seq=toks, begin=start, end=to, payload=payload)

