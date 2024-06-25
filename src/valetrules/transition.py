import re
from abc import ABC, abstractmethod
from typing import Iterator, List, Mapping, Optional, Tuple, Union, TYPE_CHECKING, cast

from nlpcore.dbfutil import GenericException
from nlpcore.tokenizer import TokenSequence
from .tokentest import TokenTest
if TYPE_CHECKING:
    from .fa import FiniteAutomaton


"""
Provides class Transition and subclasses SymbolTransition, NullTransition,
and TestTransition.
These are part of the implementation of finite automata used in implementing
token tests, phrase expressions, and parse expressions.
"""


# Note that the 'symbol' member means different things for different subclasses.
class Transition(ABC):
    """Abstract base class for an FA transition that can occur between source
    and destination states when an input (or dependency edge) token is seen.
    (NullTransition is a special case that does not require an input token.)"""

    __slots__ = ("fa", "src", "dest", "symbol")

    @staticmethod
    def new(fa: 'FiniteAutomaton', src: int, dest: int, symbol: Optional[str] = None) -> 'Transition':
        """Return new NullTransition if symbol=None, else SymbolTransition."""
        if symbol is None:
            return NullTransition(fa=fa, src=src, dest=dest, symbol=None)
        else:
            return SymbolTransition(fa=fa, src=src, dest=dest, symbol=symbol)

    # TODO? Ideally the base class wouldn't have symbol member.
    # It holds either a literal to match vs token, or the name of a token test
    # to match, or None for NullTransition.
    # src and dest state ids can be None during FA construction.
    def __init__(self, fa: 'FiniteAutomaton', src: Optional[int] = None,
                 dest: Optional[int] = None, symbol: Optional[str] = None):
        self.fa = fa
        # Make sure we have IDs and not states.
        # (None here instead of ID is usually to be filled in later,
        # when creating new FAs by splicing together others.)
        self.src = src
        self.dest = dest
        self.symbol = symbol

    @abstractmethod
    def matches(self, toks: TokenSequence, at: int,
                substitutions: Optional[Mapping[str, str]]) -> Union[str, bool]:
        """Used in FAs for phrase patterns.
        Returns truthy value if can transition to next token, else False."""
        pass

    @abstractmethod
    def arc_matches(self, toks: TokenSequence, at: int,
                    substitutions: Optional[Mapping[str, str]]) -> Iterator[int]:
        """Used in (Arc)FAs for parse patterns.
        Generates "to" token indices that can be transitioned to."""
        pass

    # Note that this is not a full clone.
    @abstractmethod
    def clone(self) -> 'Transition':
        pass

    @abstractmethod
    def generate_to(self) -> Tuple[int, List[str]]:
        pass

    def reverse(self) -> 'Transition':
        newtrans = self.clone()
        newtrans.dest = self.src
        newtrans.src = self.dest
        return newtrans

    def same(self, symbol: str, dest: int) -> bool:
        """True if symbol and dest are our symbol and destination."""
        return symbol == self.symbol and dest == self.dest

    def dumps(self, leading_str="") -> str:
        return "%s(%s) -> %s" % (leading_str, self.symbol, self.dest)

    def requirements(self, substitutions=None) -> set:
        return set()

    # NullTransition doesn't have a symbol attribute, or it's None,
    # but it doesn't call this.
    def decompose_symbol(self) -> Tuple[str, Optional[str]]:
        """From something like /nsubj, returns tuple of 'nsubj' and '/'.
        If there's no directional modifier / or \\, second value is None."""
        m = re.match(r'([/\\])(.*)', self.symbol)
        if m:
            symbol = m.group(2)
            direction = m.group(1)
        else:
            symbol = self.symbol
            direction = None
        return symbol, direction

    def __str__(self):
        return f"{self.__class__.__name__}({self.src},{self.dest},{self.symbol})"


# The 'symbol' member will be a literal token string (or edge label
# string for ArcFA, possibly with preceding direction /\); if seen,
# the transition can happen (for ArcFAs, the direction has to match too).
#
# Contrary to an earlier impression I had, this class is NOT used
# for pattern names associated with "callout" states implementing
# associated with "@" references to other parse/phrase expressions.
# Instead, the referenced pattern name is stored in the FACalloutState
# and the rule is looked up in the code branch for FACalloutState
# in the FA.match_from_state.match method.
# And hence substitute_and_lookup is called there, and is not called
# in the transition as it is for TestTransition.
class SymbolTransition(Transition):
    """Transition that can occur if literal referenced by self.symbol
    matches the input token, optionally case-insensitively."""

    __slots__ = ()

    def matches(self, toks, at, substitutions) -> bool:
        if self.fa.case_insensitive:
            return toks[at].lower() == self.symbol.lower()
        else:
            return toks[at] == self.symbol

    # Note that while matches() returns a (boolean) value,
    # arc_matches() is a generator and yields token indices,
    # which are the token indices the edges from/to 'at' connects to/from.
    def arc_matches(self, toks, at, substitutions) -> Iterator[int]:
        symbol, direction = self.decompose_symbol()
        if direction is None or direction == '/':
            # There can be 0 or 1 up dependencies.
            for toki, dep in toks.get_up_dependencies(at):
                if dep == symbol:
                    yield toki
        if direction is None or direction == '\\':
            # There can be any number of down dependencies.
            for toki, dep in toks.get_down_dependencies(at):
                if dep == symbol:
                    yield toki

    def clone(self) -> 'SymbolTransition':
        return SymbolTransition(fa=self.fa, symbol=self.symbol)

    def generate_to(self) -> Tuple[int, List[str]]:
        return self.dest, [self.symbol]


# 'symbol' member is None or absent, and is not used.
class NullTransition(Transition):
    """Transition that can occur without (and only without) consuming
    any input token."""
    # Hence if called to consume input token at "at", doesn't match.

    __slots__ = ()

    def matches(self, toks, at, substitutions) -> bool:
        return False

    # I gather the yield makes this a generator, but it is never reached.
    # So this will always generate zero results.
    def arc_matches(self, toks, at, substitutions) -> Iterator[int]:
        return
        yield

    def clone(self) -> 'NullTransition':
        return NullTransition(fa=self.fa, symbol=None)

    def generate_to(self) -> Tuple[int, List[str]]:
        return self.dest, []

    def __str__(self):
        return "NullTransition()"


# 'symbol' member is the name (LHS) of the token test.
class TestTransition(Transition):
    """Transition that can occur if token test referenced by
    self.symbol is true for the input token."""

    __slots__ = ()

    def matches(self, toks, at, substitutions) -> Union[str, bool]:
        # Making a slightly kludgy modification to the original behavior
        # of this method to support the selectability of token test matches
        # in downstream extractors. Instead of True, we return the symbol
        # (a string), which also should test true in a Boolean context.
        patname, ext, type_, merged_substitutions = self.fa.manager.substitute_and_lookup(self.symbol, substitutions)
        if type_ != "test":
            raise GenericException(f"In phrase pattern {self.fa.name}, {self.symbol} (-> {patname}) should be a token test, but is a {self.fa.manager.extractor_type_to_long_name(type_)}")
        ext = cast(TokenTest, ext)
        matched: Union[str, bool]  # always str for token test
        matched = ext.matches_at(toks, at, merged_substitutions)
        # matched could differ from patname due to substitutions,
        # but we're deciding to return patname.
        # By returning patname we're using the name as it occurs
        # in the phrase expression for the submatch, not the actual
        # name from a reference token test or a substitution.
        # See comments at ReferenceTokenTest.matches_at.
        if matched:
            return patname
        else:
            return False

    def arc_matches(self, toks, at, substitutions) -> Iterator[int]:
        symbol, direction = self.decompose_symbol()
        # An ArcFA will rarely have a token test rather than
        # a literal, but it is legal (e.g., see issue #22).
        patname, ext, type_, merged_substitutions = self.fa.manager.substitute_and_lookup(symbol, substitutions)
        if type_ != "test":
            raise GenericException(f"In phrase pattern {self.fa.name}, {symbol} (-> {patname}) should be a token test, but is a {self.fa.manager.extractor_type_to_long_name(type_)}")
        ext = cast(TokenTest, ext)
        matched: Union[str, bool]  # always str for token test arc
        if direction is None or direction == '/':
            for toki, dep in toks.get_up_dependencies(at):
                # If we wanted to make token test submatches of parse
                # expression matches, we'd return the patname too.
                # That could differ from matched due to substitutions.
                matched = ext.matches_token(dep, merged_substitutions)
                if matched:
                    yield toki
        if direction is None or direction == '\\':
            for toki, dep in toks.get_down_dependencies(at):
                matched = ext.matches_token(dep, merged_substitutions)
                if matched:
                    yield toki

    def dumps(self, leading_str=""):
        return "%s<%s> -> %s" % (leading_str, self.symbol, self.dest)

    def clone(self) -> 'TestTransition':
        return TestTransition(fa=self.fa, symbol=self.symbol)

    def generate_to(self) -> Tuple[int, List[str]]:
        try:
            ext, typ = self.fa.manager.lookup_own_extractor(self.symbol)
        except KeyError:
            raise GenericException(msg="Not a token test name: " % self.symbol)
        if typ != 'test':
            raise GenericException(msg="Not a token test name: " % self.symbol)
        emit = ext.generate(self.symbol)
        return self.dest, [emit]

    def requirements(self, substitutions=None):
        symbol, _ = self.decompose_symbol()
        _, ext, _, merged_substitutions = self.fa.manager.substitute_and_lookup(symbol, substitutions)
        return ext.requirements(substitutions)
