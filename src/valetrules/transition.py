import re
from typing import Tuple, Optional

from nlpcore.dbfutil import SimpleClass, GenericException


"""
Provides class Transition and subclasses SymbolTransition, NullTransition, 
and TestTransition.
These are part of the implementation of finite automata used in implementing 
token tests, phrase expressions, and parse expressions.
"""

# Note that the 'symbol' member means different things for different subclasses.
class Transition(SimpleClass):
    """Abstract base class for an FA transition that can occur between source and 
    destination states (referenced by name) when an input token (aka symbol) 
    is seen.
    (NullTransition is a special case that does not require an input token.)"""

    @staticmethod
    def new(fa, src, dest, symbol=None):
        """Return new NullTransition if symbol=None, else SymbolTransition."""
        if symbol is None:
            return NullTransition(fa=fa, src=src, dest=dest, symbol=None)
        else:
            return SymbolTransition(fa=fa, src=src, dest=dest, symbol=symbol)

    def __init__(self, **args):
        SimpleClass.__init__(self, **args)
        # Make sure we have IDs and not states.
        if hasattr(self, 'src'):
            self.src = self.state_id(self.src)
        if hasattr(self, 'dest'):
            self.dest = self.state_id(self.dest)

    def state_id(self, state):
        try:
            return state.id
        except:
            return state

    def reverse(self):
        newtrans = self.clone()
        newtrans.dest = self.src
        newtrans.src = self.dest
        return newtrans

    def same(self, symbol, dest):
        """True if symbol and dest are our symbol and destination."""
        return symbol == self.symbol and self.state_id(dest) == self.dest

    def dumps(self, leading_str=""):
        return "%s(%s) -> %s" % (leading_str, self.symbol, self.dest)

    def requirements(self):
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


# 'symbol' member can be a literal token value; if seen, the transition 
# can happen.
# Can also (for "callout" transitions implementing "@" expression references) 
# be the name (LHS) of the expression.
# TODO? I think that second sentence might be wrong/outdated?
class SymbolTransition(Transition):

    def __init__(self, **args):
        Transition.__init__(self, **args)
#        print "Transition: %s (%s) -> %s" % (self.src, self.symbol, self.dest)
    
    def matches(self, toks, at):
        if self.fa.case_insensitive:
            return toks[at].lower() == self.symbol.lower()
        else:
            return toks[at] == self.symbol

    # Note that while matches() returns a (boolean) value, 
    # arc_matches() is a generator and yields token indices, 
    # which are the token indices the edges from/to 'at' connects to/from.
    def arc_matches(self, toks, at):
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

    def clone(self):
        return SymbolTransition(fa=self.fa, symbol=self.symbol)

    def generate_to(self):
        return (self.dest, [self.symbol])


# 'symbol' member is None or absent, and is not used.
class NullTransition(Transition):
    
    def matches(self, toks, at):
        return False

    # I gather the yield makes this a generator, but is never reached. 
    # So this will always generate zero results.
    def arc_matches(self, toks, at):
        return
        yield

    def clone(self):
        return NullTransition(fa=self.fa, symbol=None)

    def generate_to(self):
        return (self.dest, [])

    def __str__(self):
        return "NullTransition()"


# 'symbol' member is the name (LHS) of the token test.
class TestTransition(Transition):

    def matches(self, toks, at):
        # Making a slightly kludgy modification to the behavior of this method to support the selectability
        # of token test matches in downstream extractors.  Instead of true, we return the symbol (a string), which
        # also should test true in a Boolean context.
        test = self.fa.manager.get_test(self.symbol)
        if test is None:
            raise GenericException(msg="Not a token test name: " % self.symbol)
        if test.matches_at(toks, at):
            return self.symbol
        else:
            return False

    def arc_matches(self, toks, at):
        symbol, direction = self.decompose_symbol()
        test = self.fa.manager.get_test(symbol)
        if test is None:
            raise GenericException(msg="Not a token test name: " % symbol)
        if direction is None or direction == '/':
            for toki, dep in toks.get_up_dependencies(at):
                if test.matches_token(dep):
                    yield toki
        if direction is None or direction == '\\':
            for toki, dep in toks.get_down_dependencies(at):
                if test.matches_token(dep):
                    yield toki

    def dumps(self, leading_str=""):
        return "%s<%s> -> %s" % (leading_str, self.symbol, self.dest)

    def clone(self):
        return TestTransition(fa=self.fa, symbol=self.symbol)

    def generate_to(self):
        try:
            test = self.fa.manager.get_test(self.symbol)
        except KeyError:
            raise GenericException(msg="Not a token test name: " % self.symbol)
        emit = test.generate(self.symbol)
        return self.dest, [emit]

    def requirements(self):
        symbol, direction = self.decompose_symbol()
        test = self.fa.manager.get_test(symbol)
        return test.requirements()

