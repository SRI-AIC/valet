import logging
from os.path import getmtime
import re
import sys
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union, TYPE_CHECKING, cast

from ordered_set import OrderedSet
# This is useful for deterministic order such as when debugging.
# But it's notably slower than Python's set, maybe too slow to
# normally use here in low-level code inside many levels of loops
# and recursion.
# MaybeOrderedSet = OrderedSet
MaybeOrderedSet = set

from nlpcore.dbfutil import GenericException
from nlpcore.lexicon import Lexicon
from nlpcore.annotator import Requirement

from .extractor import Extractor
from .match import FAMatch, FAArcMatch
from .state import FAState, FACalloutState
from .transition import NullTransition
if TYPE_CHECKING:
    from .manager import VRManager
    from .regex import Regex

"""
Provides FiniteAutomaton class and subclasses such as ArcFiniteAutomaton.
These implement finite automata used in implementing
token tests, phrase expressions, and parse expressions.

A finite automaton consists of an interconnected set of states and
# transitions that can be used to recognize a matching sequence of tokens.
# Key FiniteAutomaton recognition operations are match, search, and scan;
# see VRManager for an overview of what those mean.
"""


_logger = logging.getLogger(f"{__name__}.<module>")


class FiniteAutomaton(Extractor):

    # Experimenting with this.
    __slots__ = ("states", "initial", "final", "regex", "max_match", "case_insensitive", "counter")

    # Instance variables:
    # name -- Typically named after LHS of pattern.
    # manager -- VRManager we belong to; needed to find other FAs we depend on.
    # states -- Map from state id (an integer) to state.
    # initial -- Initial state.
    # final -- Map from state to whether it's final.

    # Our builtin FAs don't need a manager, so allow defaulting here.
    def __init__(self, manager: Optional['VRManager'] = None,
                 max_match: int = 300, case_insensitive: bool = False,
                 regex: Optional['Regex'] = None,
                 **kwargs):
        # Apparently this is only getting set via Extractor.set_name.
        # if "name" in kwargs:
        #     raise Exception(f"'name' in kwargs")
        super().__init__(manager, **kwargs)
        # Max number tokens from the starting point we will consider
        # when matching. Presumably defends against inadvertently incorrect
        # or perhaps overly expensive patterns, or unusually long
        # token sequences.
        self.max_match = max_match
        self.case_insensitive = case_insensitive
        # Note that most FAs also get assigned (via ctor or otherwise)
        # a regex: Regex field, used in references().
        self.regex = regex  # regex this fa was derived from
        self.counter: int = 0  # used in assigning numeric IDs to states of the FA
        self.states: Dict[int, FAState] = {}
        self.initial: FAState = FAState(parent=self)
        self.final: Dict[int, bool] = {self.initial.id: True}  # why initial? partly for START/END

    def get_state(self, sid: int) -> FAState:
        """Get state by its id."""
        return self.states[sid]

    # Sometimes when manipulating FAs, a corresponding state from a different
    # FA is passed, making the state with the same id final in this FA.
    def make_final(self, state: FAState, final: bool = True) -> None:
        """Set the state's final status, by its id."""
        self.final[state.id] = final

    def is_final(self, state: FAState):
        sid = state.id
        return sid in self.final and self.final[sid]

    def get_final_states(self) -> List[FAState]:
        return [self.states[sid] for sid, f in self.final.items() if f]

    def dump(self) -> None:
        """
        Print a human-readable representation of the FA showing states
        and transitions.
        > indicates an initial state and @ a final state.
        """
        print(self.dumps())

    def dumps(self) -> str:
        """
        Print a human-readable representation of the FA showing states
        and transitions.
        > indicates an initial state and @ a final state.
        """

        # used to track which transitions have been visited
        visited = {}

        def do_dumps(state: FAState):
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
                    s.extend(do_dumps(self.states[trans.dest]))
            return s

        return "".join(do_dumps(self.initial))

    ###########################################################################
    # BUILDING FAs
    #

    # The methods atom, concat, altern, star/plus/opt are typically used
    # to initialize a newly created FA.
    # They're called from, eg, the fa() methods of regex.Regex's.

    def atom(self, symbol) -> 'FiniteAutomaton':  # self
        """
        If the symbol starts with a reference symbol ('&' or '@'):
            add a test transition if a test of the indicated name exists
            else add a callout transition
        Else a literal transition
        """
        m = re.match(r'[&@]([/\\]?)(\w+(?:\.\w+)*)$', symbol)
        if m:
            arc_dir = m.group(1)
            name = m.group(2)
            # At one point this did not recognize imported token tests,
            # so a callout transition got added instead of a test transition.
            # The code still worked (to our surprise), but I think was
            # a bit less efficient?
            # See also comments in FA.match_from_state.match.
            is_token_test = self.manager.test_is_defined(name)
            if is_token_test:
                final = self.initial.add_test_transition(symbol[1:])
            elif len(arc_dir) > 0:
                # The logic and wording here seemed peculiar at first glance.
                # Doesn't the present situation mean we have a callout?
                # Can't we have a direction on a callout in a parse rule?
                # I guess not, and the reason is probably that so far
                # direction is considered to apply only to a single edge,
                # and not to a path.
                # I could imagine a callout to another parse rule that
                # can match multiple edges, and maybe we could extend
                # the direction concept to that in a sensible way,
                # but we don't have a real need for that yet.
                # Updating error message to allow for a user thinking
                # that's possible (I didn't know it wasn't).
                # raise GenericException(msg="Direction '%s' specified on missing test (%s)" % (arc_dir, name))
                raise GenericException(msg="Direction '%s' specified on missing test (%s), or on non-test rule reference" % (arc_dir, name))
            else:
                final = self.initial.add_callout_transition(symbol[1:])
        else:
            # The direction marker, if any, is still attached to the symbol.
            final = self.initial.add_transition(symbol)
        self.make_final(self.initial, False)
        self.make_final(final)
        return self

    # def atom_old(self, symbol):
    #     """Make the FA represent a token test reference (symbol = "&ttname"),
    #     expression reference (symbol = "@exname"), or string literal (symbol =
    #     anything else)."""
    #     if re.match(r'&[/\\]?(\w|\.)+$', symbol):
    #         final = self.initial.add_test_transition(symbol[1:])
    #     elif re.match(r'@(\w|\.)+$', symbol):
    #         final = self.initial.add_callout_transition(symbol[1:])
    #     else:
    #         final = self.initial.add_transition(symbol)
    #     self.make_final(self.initial, False)
    #     self.make_final(final)
    #     return self

    def concat(self, fas: Iterable['FiniteAutomaton']) -> 'FiniteAutomaton':  # self
        """Appears to roughly copy the other FAs and assemble them into
        a larger one "in series", connected by null transitions."""
        statemap: Dict[int, FAState]
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

    def altern(self, fas: Iterable['FiniteAutomaton']) -> 'FiniteAutomaton':  # self
        """Appears to roughly copy the other FAs and assemble them into
        a larger one "in parallel", connected by null transitions."""
        final = self.get_final_states()
        for state in final:
            self.make_final(state, False)
        for fa in fas:
            init = fa.initial
            statemap: Dict[int, FAState] = self.eat(fa)
            init = statemap[init.id]
            for state in final:
                state.add_unique_transition(None, init)
            for state in fa.get_final_states():
                self.make_final(statemap[state.id])
        return self

    def star(self) -> 'FiniteAutomaton':  # self
        """Implemented as plus() followed by opt()."""
        return self.plus().opt()

    def plus(self) -> 'FiniteAutomaton':  # self
        """Add null transitions from all final states back to initial state
        (expresses arbitrary number of repetitions)."""
        init = self.initial
        final = self.get_final_states()
        for state in final:
            state.add_unique_transition(None, init)
        return self

    def opt(self) -> 'FiniteAutomaton':  # self
        """Add null transitions from initial state to all final states
        (expresses optionality)."""
        init = self.initial
        final = self.get_final_states()
        for state in final:
            init.add_unique_transition(None, state)
        return self

    def eat(self, fa: 'FiniteAutomaton') -> Dict[int, FAState]:
        """Appears to roughly clone the state map of the other FA,
        making the cloned states and transitions children of "self"."""
        statemap: Dict[int, FAState]
        statemap = dict((s.id, s.clone(self))
                        for s in fa.states.values())
        for sid, newstate in statemap.items():
            state = fa.states[sid]
            for trans in state.transitions:
                newtrans = trans.clone()
                newtrans.src = newstate.id
                newtrans.dest = statemap[trans.dest].id
                newtrans.fa = self
                newstate.transitions.append(newtrans)
        return statemap

    # Experimenting with not cloning, which changes the IDs, just re-parenting
    # the states and transitions.
    # Seems to work fine [at the time, but very possibly not tested in enough
    # different situations].
    # TODO? Perhaps use this instead if it makes sense, or get rid of it
    # if it doesn't?
    # This was written by Bob early, long before we had a lot of unit tests,
    # plus there have been a lot of changes since then.
    # Trying it out in 4/2024, we get a lot of test failures.
    # Would be interesting to look into why, but not justifiable right now.
    # def eat_new(self, fa: 'FiniteAutomaton'):
    #     """Re-parent the states and transitions of fa from fa to self."""
    #     statemap = dict((s.id, s)
    #                     for s in fa.states.values())
    #     for sid, state in statemap.items():
    #         state.parent = self
    #         self.states[sid] = state
    #         for trans in state.transitions:
    #             trans.fa = self
    #     return statemap

#     def add_path(self, items):
#         state = self.initial
#         for item in items:
#             next_state = state.transition(item)
#             if not next_state:
#                 next_state = state.add_unique_transition(item)
#                 next_state.label = item
#             state = next_state
#             state.incr()

    # TODO? Might consider returning more detailed info like at which state
    # and transition the loopiness is first discovered.
    def loopy(self):
        """Method that check for loops, used in debugging patterns."""

        visited = {}

        def loopy_at_state(state):
            if state.id in visited:
                return True
            visited[state.id] = True
            for trans in state.transitions:
                next_state = self.states[trans.dest]
                if loopy_at_state(next_state):
                    return True
            return False

        return loopy_at_state(self.initial)

    # Note that this is not a full clone.
    def clone(self) -> 'FiniteAutomaton':
        fa = FiniteAutomaton(manager=self.manager)
        for sid, state in self.states.items():
            fa.states[sid] = state.clone(fa)
            if state == self.initial:
                fa.initial = fa.states[sid]
        return fa

    # The reversed FA concept is not active anymore, 
    # but we now have tests for it.
    # See also manager.get_reversed_fa.
    def reverse(self) -> 'FiniteAutomaton':
        """Return a new FA that matches the same sequences as the current one,
        but in reversed token order."""

        fa = self.clone()

        # Reverse all transitions
        for sid, state in self.states.items():

            # Erase finality for now.  We'll designate a final state below.
            fa.make_final(fa.states[sid], False)

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
        fa.make_final(fa.states[self.initial.id], True)

        return fa

    ###########################################################################
    # RUNNING FAs
    #

    # Regarding all the null transitions, Dayne said that there are
    # so many of them because they're convenient to enable building up
    # larger FAs out of smaller independent constituents in a
    # straightforward way.
    # For example, see the atom, concat, altern, star/plus/opt methods
    # of this class.
    def null_transitive_closure(self, sids: Iterable[int]) -> Set[int]:
        """ Gives the transitive closure, under null transitions only,
        of the collection of state ids."""
        sids = MaybeOrderedSet(sids)
        # First follow all single null transitions from the states.
        newsids = MaybeOrderedSet(t.dest for s in sids for t in self.states[s].transitions
                                  if isinstance(t, NullTransition) and t.dest not in sids)
        # Now quasi-recursively follow all null transitions, except ones
        # from callout states, since we've not descended into those yet.
        while len(newsids) > 0:
            sids |= newsids
            newstates = (self.states[s] for s in newsids)
            # You'd think checking s's type before looping over its transitions
            # would be faster, but it depends on the distribution of callouts
            # in the rules vs token tests or literals, and on FA structure,
            # so not necessarily.
            newsids = MaybeOrderedSet(t.dest for s in newstates for t in s.transitions
                                      if isinstance(t, NullTransition) and t.dest not in sids
                                      and not isinstance(s, FACalloutState))
        return sids

    def match_from_state(self, toks, sid, start, end, substitutions=None):
        """Generator matching this FA against tokens, starting at specified
        start token, starting from specified state, potentially generating
        multiple matches if there are multiple ways to match."""
        ## print(" In %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

        def match(at: int, state: FAState):
            """Generator matching this FA against tokens
            (having started at start token specified by match_from_state),
            continuing from specified state and at token, potentially
            generating multiple matches if there are multiple ways to match.
            Generates match object with end value showing how far in tokens
            we could match (if we could match up to a final state)."""
            # nonlocal toks, start, end, substitutions

            ## print("  In %s.match_from_state.match(at=%d, state=%s)" % (self.name, at, state))
            if at > end or at - start > self.max_match:
                return  # FWIW this is not hit in unit tests
            # just use for debug msgs; at can = end when we recurse one time too many
            # tok = toks[at] if at < end else None

            if isinstance(state, FACalloutState):
                cast(FACalloutState, state)
                # FACalloutState is used for references from one phrase
                # expression to another (using @&).
                # "Descend" into the FA for that and match against it.
                ## print("   Descending into %s at token %d '%s'" % (state, at, tok))

                assert not state.reversed
                # if state.reversed:
                    # We're scanning backward, and need an inverted FA. (We don't do that anymore.)
                    # fa = self.manager.get_reversed_fa(state.symbol)
                # fa = self.manager.get_fa(state.symbol)

                # Before calling out through manager.matches further below,
                # make sure we're calling out to a pattern type that
                # makes sense from a (non-Arc) FA.
                # (There used to be more restrictions.)
                # manager.matches will apply any substitutions too, but
                # to check the actual type in the presence of substitutions,
                # we need to do so here as well.
                # Also, note substituted patname is used below when assigning
                # submatch patnames.
                patname = state.symbol
                patname, _, type_, _ = self.manager.substitute_and_lookup(patname, substitutions=substitutions)
                if type_ is None:
                    raise GenericException(msg="Could not resolve reference to '%s'; is that really the name of a pattern?" % state.symbol)
                elif type_ == "test":
                    # Code should have taken the non-callout branch in this case.
                    # See comments in FA.atom near test_is_defined.
                    # Interestingly, the code still works correctly this way,
                    # so fall through.
                    # TODO? I think this can now happen in the presence of
                    # misguided or accidental type_-changing substitutions,
                    # so should update this message. Also in ArcFA.
                    # raise GenericException(msg="Code should not get here for a token test (%s)" % state.symbol)
                    print(f"Code should not get here for a token test: {state.symbol} (-> {patname})")  # debug
                elif type_ == "dep_fa":
                    # We could have a coordinator or frame referencing
                    # a parse rule, so this is not a foolproof check.
                    raise GenericException(msg="'%s' (-> %s) reference in phrase expression may not refer to a parse expression." % (state.symbol, patname))
                # else fas, coords, frames all now allowed

                ## matched1 = False
                # quasi-recurse into the referenced FA (or other extractor)
                for sm in self.manager.matches(state.symbol, toks, at, end, substitutions):
                    smbegin, smend = sm.get_extent()
                    # Avoid bizarre behavior that could result if
                    # a phrase extractor calls a parse extractor
                    # (wrapped in a coordinator or frame)
                    # that returns reversed match endpoints.
                    # We only use submatches that advance us
                    # in the token sequence.
                    if smbegin < at or smend < at:
                        print(f"Questionable pattern usage: callout from '{self.name}' to '{state.symbol}' returned match [{smbegin},{smend}) that includes tokens before the current token {at}; are you mixing phrase and parse patterns?", file=sys.stderr)
                        continue

                    ## matched1 = True
                    # FWIW, it appears that we no longer need to assign
                    # the submatch name here, as it's always coming back
                    # the same as patname, since manager.matches assigns it.
                    # if not hasattr(sm, "name"):
                    #     _logger.info("Submatch has no name attr")
                    # elif sm.name is None:
                    #     _logger.info("Submatch name is None")
                    # elif sm.name != patname:
                    #     _logger.info("Submatch name is {sm.name}, not {patname}")
                    sm.name = patname
                    if self.is_final(state):
                        # We never see this. Probably FAs are set up
                        # such that callout states are never final.
                        print("  ## Matched", patname, "with submatch", sm)
                        yield FAMatch(seq=toks, begin=start, end=smend, submatches=[sm], name=self.name)

                    # Regardless of whether state is final and we yielded
                    # a match, might still be able to continue matching
                    # from here and get to another final state.
                    dest1: Iterable[int] = state.null_transition_to()
                    ## if len(dest) == 0:
                    ##     print("   No null transitions from state %d available to continue matching" % state.id)
                    # print("Trying null transitions from", str(state.id), "to", dest)
                    for sid in dest1:
                        ## print("   Trying null transition from state %d to %d" % (state.id, sid))
                        ## matched2 = False
                        deststate = self.states[sid]
                        for m in match(smend, deststate):  # recurse from where last match left off
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
                # First try to consume a token and recurse as long as
                # we can do so.
                if at < end:
                    # str's are from token test matches; True's from literals.
                    dest2: Mapping[int, Set[Union[str, bool]]] = \
                        state.transition_to(toks, at, substitutions)
                    ## if len(dest2) == 0:
                    ##     print("   Unable to consume token %d '%s' from state %d" % (at, tok, state.id))
                    # if len(dest2) > 0:
                    #     print("Transitioning from state", str(state.id), "to", dest, "on token=" + tok)
                    # dest2 is now a dict mapping state IDs to all
                    # transition.matches returns that got us to them.
                    for sid, transition_matches in dest2.items():
                        # TODO? We end up throwing these submatches away
                        # if the recursion below does not succeed.
                        submatches = [FAMatch(seq=toks, begin=at, end=at+1, name=tm)
                                      for tm in transition_matches if isinstance(tm, str)]
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
                # Note that we create the match object here without submatches,
                # then as the stack is unwound we add each submatch to it,
                # in reverse order, in the block of code above.
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
            # print(" # Yielding %s from call to match(at=%s,state=%s)" % (m, start, state))
            yield m
        # if not matched:
        #     print("No match from sid=%d start=%s end=%s" % (sid, start, end))
        ## print(" Leaving %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

    def matches(self, toks, start=0, end=None, substitutions=None):
        """Generator matching this FA against tokens, starting only
        at specified start token, starting from initial state,
        potentially generating multiple matches if there are multiple ways
        to match. Drops zero-length matches."""
        if end is None:
            end = len(toks)
        states = self.null_transitive_closure([self.initial.id])
        ## print("In %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))
        for sid in states:
            for m in self.match_from_state(toks, sid, start, end, substitutions):
                # m.end == m.start (== start) can happen for zero-length
                # matches from *, ?, and presumably @START/@END.
                # Not sure about @ROOT.
                if m.end != start:
                    ## print("%s.matches(tokens, start=%d) found match %s from state %d" % (self.name, start, m, sid))
                    yield m
                ## else:
                ##    print("DEBUG: name=%s m.end=%d == start=%d" % (self.name, m.end, start))
        ## print("Leaving %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))

    def match(self, toks, start=0, end=None, subst=None):
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
        matches = [m for m in self.matches(toks, start, end, subst)
                   if m.end >= m.begin]

        if len(matches) > 0:
            mx = max(matches, key=lambda m: m.end)
            # print("Returning longest match for self:", self.name + ":" + str(mx.begin) + ":" + str(mx.end))
            return mx
        else:
            return None

    def search(self, toks, start=0, end=None, subst=None):
        """Match this FA against tokens, starting at every starting point
        from start on, returning the longest match found from the first
        starting point where there is a match, or None."""
        # print("In", self.name + ".search(tokens, start=" + str(start) + ", end=" + str(end) + ")")
        if end is None:
            end = len(toks)
        while start < end:
            m = self.match(toks, start, end, subst)
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
    def scan(self, toks, start=0, end=None, substitutions=None):
        """
        Generate matches falling within specified start/end range, but choosing
        only the longest match at any starting point, and starting search
        for the next match where the last one stopped.
        """
        # print("In", self.name + ".scan(tokens=" + str(toks.tokens) + ", start=" + str(start) + " end=" + str(end) + ")")
        # self.dump()
        m = self.search(toks, start, end, substitutions)
        while m:
            yield m
            start = m.end  # start next search where last one stopped
            # Trying to fix matching of START in test_phrase.py,
            # but didn't work as hoped. Still working on that issue.
            # start = min(start+1, m.end)  # start next search where last one stopped
            m = self.search(toks, start, end, substitutions)


    ###########################################################################
    # OTHER
    #

    def generate_to(self) -> Tuple[int, List[str]]:
        state = self.initial
        result = []
        trans: Optional[Tuple[int, List[str]]] = state.generate_to()
        while trans is not None:
            next_sid, emits = trans
            result.extend(emits)
            state = self.states[next_sid]
            trans = state.generate_to()
        return state.id, result

    def generate(self) -> List[str]:
        sid, emits = self.generate_to()
        return emits

    # Caller is from_fsm in our regex.py.
    def breadth_first_traversal(self) -> List[FAState]:
        sids: List[int] = [self.initial.id]
        states: List[FAState] = []
        i = 0
        while i < len(sids):
            current: FAState = self.states[sids[i]]
            states.append(current)
            for t in current.transitions:
                if t.dest not in sids:
                    sids.append(t.dest)
            i += 1
        return states

    def traverse(self) -> List[FAState]:
        sids: List[int] = [self.initial.id]
        i = 0
        while i < len(sids):
            current: FAState = self.states[sids[i]]
            yield current
            for t in current.transitions:
                if t.dest not in sids:
                    sids.append(t.dest)
            i += 1

    def requirements(self, substitutions=None) -> Set[Requirement]:
        req = set()
        # TODO? Is there some reason why we can't do this instead?
        # just use self.states.values()? Apparently not.
        states = list(self.traverse())
        # states0 = set(self.states.values())
        # bstates = self.breadth_first_traversal()
        # if set(states) != states0:
        #     raise(Exception("Unexpected"))
        # if set(bstates) != states0:
        #     raise(Exception("Unexpected"))
        for s in states:
            req |= s.requirements(substitutions)
        return req

    def references(self):
        return self.regex.references()

    def __str__(self):
        return f"FA(name={getattr(self, 'name', None)})"
        # return f"{object.__str__(self)}[name={getattr(self, 'name', None)}]"


class ArcFiniteAutomaton(FiniteAutomaton):

    __slots__ = ()

    def match_from_state(self, toks, sid, start, end, substitutions=None):
        """Generator matching this FA over the dependency graph, starting
        at specified start token, starting from specified state,
        potentially generating multiple matches if there are multiple ways
        to match."""
        ## print(" In %s.match_from_state(tokens, sid=%d, start=%d, end=%d)" % (self.name, sid, start, end))

        # TODO See issue #29.
        # I (Bob) suspect the visited logic here is not really correct.
        # I suspect that rather than looking at not revisiting (state.id, at)
        # combinations, we need to look at not re-traversing arcs of the
        # dependency graph (or something along those lines).
        def match(at: int, state: FAState, visited=set()):
            """Generator matching this FA against dependency graph
            (having started at start token specified by match_from_state),
            continuing from specified state and at token, potentially
            generating multiple matches if there are multiple ways to match.
            Generates match object with end value showing how far in tokens
            we could match (if we could match up to a final state)."""

            ## print("  In %s.match_from_state.match(at=%d, state=%s)" % (self.name, at, state))
            if at > end or at - start > self.max_match:
                return  # FWIW this is not hit in unit tests
            # just for debug; not sure if at can = end in arc FAs
            # tok = toks[at] if at < end else None
            # print("In FAArcMatch.match, tok=%s" % tok)

            # Disallow repeat visits to a state (from a given 'at' value).
            # (Not needed for regular FA since can't go backward in those.)
            if (state.id, at) in visited:
                return
            visited |= set([(state.id, at)])

            if isinstance(state, FACalloutState):
                cast(FACalloutState, state)
                # FACalloutState is used for references from one parse
                # expression to another (using @&).
                # "Descend" into the FA for that and match against it.
                ## print("   Descending into %s at token %d '%s'" % (state, at, tok))

                # Before calling out through manager.matches further below,
                # make sure we're calling out to a pattern type that
                # makes sense from a ArcFA.
                patname = state.symbol
                # manager.matches will apply any substitutions too, but
                # to check the actual type in the presence of substitutions,
                # we need to do so here as well.
                # Also, note substituted patname is used below when assigning
                # submatch patnames.
                patname, _, type_, _ = self.manager.substitute_and_lookup(patname, substitutions=substitutions)
                if type_ is None:
                    raise GenericException(msg="Could not resolve reference to '%s'; is that really the name of a pattern?" % state.symbol)
                elif type_ == "test":
                    # Code should have taken the non-callout branch in this case.
                    # raise GenericException(msg="Code should not get here for a token test (%s)" % state.symbol)
                    # See comment in FA code.
                    print(f"Code should not get here for a token test: {state.symbol} (-> {patname})")  # debug
                elif type_ != "dep_fa":
                    # TODO Probably don't want a phrase FA, but why not
                    # coordinator or frame?
                    # Is that only because they can refer to phrase FAs?
                    raise GenericException(msg="'%s' (-> %s) reference in parse expression must refer to another parse expression or to a token test expression, but it refers to a %s expression." % (state.symbol, patname, self.manager.extractor_type_to_long_name(type_)))

                # quasi-recurse into referenced arc FA (or token test)
                for sm in self.manager.matches(state.symbol, toks, at, end, substitutions):
                    # FWIW, it appears that we no longer need to assign
                    # the submatch name here, as it's always coming back
                    # the same as patname, since manager.matches assigns it.
                    # if not hasattr(sm, "name"):
                    #     _logger.info("Submatch has no name attr")
                    # elif sm.name is None:
                    #     _logger.info("Submatch name is None")
                    # elif sm.name != patname:
                    #     _logger.info("Submatch name is {sm.name}, not {patname}")
                    sm.name = patname
                    if self.is_final(state):
                        # We never see this. Probably ArcFAs are set up
                        # such that callout states are never final.
                        print("  ## ArcFA matched", patname, "with submatch", sm)
                        yield FAArcMatch(seq=toks, begin=start, end=sm.end, submatches=[sm], name=self.name)

                    # As in FA, try to continue matching from sm.end.
                    dest1: Iterable[int] = state.null_transition_to()
                    for sid in dest1:
                        deststate = self.states[sid]
                        for m in match(sm.end, deststate, visited):
                            # print("  ## Adding arc submatch %s to %s" % (sm, m))
                            m.add_submatch(sm)
                            yield m
            else:
                # Regular state, try to transition, consuming one token
                # (arc label).
                # First try to consume a token and recurse as long as
                # we can do so.
                if at < end:
                    next_states: Iterable[Tuple[int, int]] = \
                        state.transit_arcs_to(toks, at, substitutions)
                    for sid, toki in next_states:
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
    def matches(self, toks, start=0, end=None, substitutions=None):
        """Generator matching this FA against tokens, starting only
        at specified start token, starting from initial state,
        potentially generating multiple matches if there are multiple ways
        to match. Drops zero-length matches."""
        if end is None:
            end = len(toks)
        states = self.null_transitive_closure([self.initial.id])
        ## print("In %s.matches(tokens, start=%d, initialStates=%s)" % (self.name, start, states))
        for sid in states:
            for m in self.match_from_state(toks, sid, start, end, substitutions):
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

    def scan(self, toks, start=0, end=None, substitutions=None):
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
            for m in self.matches(toks, start, end, substitutions):
                # When the scan method was added, we initially required
                # m.end >= m.begin here in order to yield a match.
                # Dayne wrote that
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

    def requirements(self, substitutions=None) -> Set[Requirement]:
        req = super().requirements(substitutions)
        req.add(Requirement.DEPPARSE)
        return req

    def __str__(self):
        return f"ArcFA(name={getattr(self, 'name', None)})"
        # return f"{object.__str__(self)}[name={getattr(self, 'name', None)}]"


# Note FWIW that these next three classes are used only for phrase expressions
# (see START/END/ROOT in VRManager).
# TODO? Would it make any sense to have versions of them for parse expressions?
#
# Note that the matches methods are used for "callouts" from one phrase
# (or parse) expression to another, which is the primary use of these
# classes (or at least of the first two), rather than being called
# at top level themselves.
#
# TODO? For completeness, might want to give these two (or three) classes
# scan methods; otherwise they inherit parent class methods.
# That may be why they didn't work as expected at top level in unit tests,
# now commented out.


class SequenceStartFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in START phrase extractor."""

    __slots__ = ()

    def matches(self, toks, start=0, end=None, substitutions=None):
        if start == 0:
            m = FAMatch(seq=toks, begin=start, end=start, name="START")
            ## print("    # Yielding %s" % m)
            yield m


class SequenceEndFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in END phrase extractor."""

    __slots__ = ()

    def matches(self, toks, start=0, end=None, substitutions=None):
        if start == len(toks):
            m = FAMatch(seq=toks, begin=start, end=start, name="END")
            ## print("    # Yielding %s" % m)
            yield m


# The point of this is to identify the root verb in the parse tree
# (or whatever the root word is if the tseq is a sentence fragment).
# Note that somewhat counterintuitively, this is an FA, not an ArcFA.
class ParseRootFiniteAutomaton(FiniteAutomaton):
    """Implements the built-in ROOT phrase extractor that matches
    a sentence's head words."""

    __slots__ = ()

    def matches(self, toks, start=0, end=None, substitutions=None):
        if end is None:
            end = len(toks)
        matches = False
        for at in range(start, end):
            if toks.is_root_token(at):
                matches = True
                # continue looping to find consecutive root tokens,
                # and put them all in a single match
            else:
                if matches:
                    yield FAMatch(seq=toks, begin=start, end=at, name="ROOT")
                return

    def requirements(self, substitutions=None) -> Set[Requirement]:
        return set([Requirement.DEPPARSE])


class LexiconMatcher(FiniteAutomaton):
    """
    A FiniteAutomaton subclass supporting literal phrase expressions.
    Wraps nlpcore's Lexicon, provides a matches() method implemented via
    Lexicon, inheriting most other methods (e.g., scan()) from superclass.
    """

    __slots__ = ("lexicon",)

    LEXICONS = {}

    @classmethod
    def load_lexicon(cls, lexicon_file, case_insensitive, is_csv, target_column, manager) -> Lexicon:
        """
        Convenience method to load literal phrase lexicons from file.
        Also caches results to avoid reading in multiple times,
        while noticing file updates.
        """
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
        # deliberately not calling superclass init
        self.manager = manager
        self.lexicon = self.load_lexicon(lexicon_file, case_insensitive, is_csv, target_column, manager)

    def requirements(self, substitutions=None) -> Set[Requirement]:
        return set()

    def references(self) -> OrderedSet[str]:
        return OrderedSet()

    def matches(self, toks, start=0, end=None, substitutions=None):
        for to, payload in self.lexicon.matches(toks, start, end):
            yield FAMatch(seq=toks, begin=start, end=to, payload=payload)
