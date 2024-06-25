from abc import ABC, abstractmethod
from typing import Iterator, Mapping, Optional, Set, TYPE_CHECKING

from ordered_set import OrderedSet

from nlpcore.annotator import Requirement
from .match import Match
if TYPE_CHECKING:
    from .manager import VRManager


# Extractor is a base class retrofitted into existing extractor types
# like TokenTest, FiniteAutomaton, ArcFiniteAutomaton, Coordinator,
# and FrameExtractor.
#
# The main purpose of the class is to clarify the methods supported
# by all extractors, and their common semantics.
#
# Some writer on OOP refers to the utility of introducing new classes
# that encapsulate particular bits of data and provide methods for
# working with it, as opposed to having the contents of those methods
# occurring across widespread locations within other classes.
# The author states that such classes often become "behavior attractors"
# that provide a good and easily identifiable place to centralize or add
# additional behaviors related to that data.
#
# One reason I want to define this class is to provide a kind of
# "documentation attractor" where information about what is common
# to extractors can be placed, and looked for.
# This includes both the abstract method definitions here,
# but also docstring documentation and also just comments providing
# additional information, background, and even discussion.




# When creating this class, I dropped the obsolete bounds arguments passed
# to methods like scan and matches in certain extractor classes, in order
# to define abstract methods for them here, since these arguments are not
# used at all, never were (except possibly briefly in the original, alternate
# semantics of Sequence{Start,End}FiniteAutomaton), and were not even present
# in other extractor classes' methods.
#
# Ironically, this was partly motiviated by the possible future need to
# add back some additional bounds-like arguments.
# But dropping the unused ones now clears the field for those changes
# if needed, and allows all the current extractors to take the same
# arguments.
#
# A particular motivation for dropping the bounds parameters was that
# where they were present, they were placed before the substitutions
# parameter in the argument list, but calls to other extractors that
# did not have a bounds parameter were often made with the substitutions
# parameter passed positionally.
#
# Besides the possible need for bounds parameters to handle alternate
# Sequence{Start,End}FiniteAutomaton semantics, there is a second
# possible need.
# TODO? The existing start/end parameters are somewhat overloaded in
# meaning and may not cover all needs, even currently.
#
# For example, the basic idea of the matches() method is to check for
# a match that starts at the 'start' index and ends no later than the
# 'end' index.
# But since parse extractors can match backwards to indices earlier
# than 'start', there is no way to specify an index such that a match
# should end no earlier than that index.
# I believe there are potentially other similar issues as well.
#
#
# Comments originally from FiniteAutomaton class:
#
# AFAICT the "bounds" args to methods like scan, search, and match
# are never passed as anything but None, and are never checked
# except by Sequence{Start,End}FiniteAutomaton.
# The bounds args are intended to support matching phrase expressions
# with @START/@END against token SUBsequences via coordinators.
# TODO We'd need to start passing bounds args from coordinators,
# and pass them along through intermediate methods.
# Currently some of those methods don't even accept bounds args.
#
#
# Comments originally from VRManager._scan(self, name, ext, type_, toks, start=0, end=None, substitutions=None):
    # TODO? We may ultimately want to accept a bounds args here.
    # E.g., in MatchCoordinator.scan, passing bounds to VRManager.scan
    # would let phrase patterns implement the alternate START/END semantics.
    # FAs and ArcFAs already accept a bounds arg.
    # Token tests and coordinators currently do not.
    # OTOH, some of our current thinking is that we may not need a bounds arg,
    # because we'll always want the bounds to be either the start/end args,
    # or 0/len(toks), and we may have separate SSTART/SEND (nominal names)
    # predefined patterns to implement that semantics.
#
#
# Old comments from the vicinity of Sequence{Start,End}FiniteAutomaton:
#
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
#
#
# Old code from Sequence{Start,End}FiniteAutomaton.matches, respectively.
# This was notionally to implement the alternate semantics of the
# possible SSTART/SEND (nominal names).
    # def matches(self, toks, start=0, end=None, substitutions=None):
    #     if bounds is not None:
    #         raise GenericException(msg="bounds passed as non-None")  # debug
    #         if start == bounds[0]:  # bounds start
    #             yield FAMatch(seq=toks, begin=start, end=start, name="START")
    # def matches(self, toks, start=0, end=None, substitutions=None):
    #     if bounds is not None:
    #         raise GenericException(msg="bounds passed as non-None")  # debug
    #         if start == bounds[1]:  # bounds end
    #             yield FAMatch(seq=toks, begin=start, end=start, name="END")



class Extractor(ABC):

    __slots__ = ("manager", "name", "substitutions")

    # Built-in extractors, and extractors of types that can't reference other
    # named extractors, like LookupTokenTest, currently have mgr=None.
    # Could change that to the manager that holds them, but little point,
    # and probably don't want to do that for built-ins, so that we only need
    # one instance of each one (although we currently actually make new ones
    # in each manager).
    def __init__(self, manager: Optional['VRManager'], name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        self.name = name

    def set_name(self, name) -> None:
        self.name = name

    def set_substitutions(self, substitutions: Optional[Mapping[str, str]]) -> None:
        self.substitutions = substitutions


    # Concrete methods providing a kind of degenerate behavior
    # for subclasses that don't need to provide something more
    # specific themselves.

    # This specifies which NLP components need to be loaded in order for
    # the rule to run properly.
    def requirements(self, substitutions: Optional[Mapping[str, str]] = None
                     ) -> Set[Requirement]:
        """
        NLP operations needed to provide information used by this extractor.
        """
        return set()

    # This is used by the GUI for underlining references to other rules
    # when you hover over their names, etc.
    # Return OrderedSet to help make the results more sensibly ordered
    # for human consumption.
    def references(self) -> OrderedSet[str]:
        """
        Names of other extractors directly referred to in the definition
        of this extractor.
        """
        return OrderedSet()


    # TODO Provide docstrings for matches() and scan().
    # At this level, the descriptions would have to be fairly generic,
    # but there should be some commonalitites.
    # But note the issues described in comments above regarding the
    # complexities introduced by parse extractors matching backward.

    @abstractmethod
    def matches(self, seq, start=0, end=None, substitutions=None) -> Iterator[Match]:
        pass

    @abstractmethod
    def scan(self, seq, start=0, end=None, substitutions=None) -> Iterator[Match]:
        pass
