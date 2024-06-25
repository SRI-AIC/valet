from abc import ABC, abstractmethod
import re
from typing import Iterator, Mapping, Optional, Union, TYPE_CHECKING

from nlpcore.dbfutil import GenericException

from .extractor import Extractor
from .tokentest import TokenTestExpression, TokenTest
from .regex import Regex, RegexExpression
from .fa import FiniteAutomaton, ArcFiniteAutomaton
from .coordinator import Coordinator
from .coordinatorexp import CoordinatorExpression
from .frame import FrameExpression, FrameExtractor
if TYPE_CHECKING:
    from .manager import VRManager

"""
Provides the StatementParser class, which takes a text string with 
definitions in the VR pattern language, and parses it into regions 
representing individual definitions. 

Each region is represented by a StatementRegion class or subclass instance.
Subclasses include BrokenRegion, CommentRegion, TestExpressionRegion, 
PhraseExpressionRegion, ParseExpressionRegion, CoordRegion, FrameRegion, etc.

Region classes are associated with a similar (but not identical) taxonomy 
of Expression classes (and related ones like FiniteAutomaton) typically 
defined in individual modules including tokentest, fa, coordinatorexp, frame, 
etc.
"""


class StatementParser(object):

    MACRO_EXPRESSION = r'(\w+\(.*?\))\s*=\s*(.*)'
    MACRO = re.compile(MACRO_EXPRESSION)
    STATEMENT_EXPRESSION = r'\s*(\w+)\s*(i?->|L[ic\d]*->|:|<-|~|\^|\$)\s*(\[.*?\])?\s*(.*)'
    STATEMENT = re.compile(STATEMENT_EXPRESSION)

    def __init__(self, text):
        self.text = text
        self.spec_start = None  # spec is the part to the left of the delimiter
        self.spec_end = None
        self.expression_start = None
        self.expression_end = None
        self.op_expr = None  # aka delimiter
        self.subst_expr = None
        self.scope: Optional[ImportRegion] = None
        self.scope_indent = None
        self.lines = None
        self.offset = None

    def _reset_parse_state(self, reset_scope=False) -> None:
        self.spec_start = None
        self.spec_end = None
        self.expression_start = None
        self.expression_end = None
        self.op_expr = None
        self.subst_expr = None
        if reset_scope:
            self.scope = None
            self.scope_indent = None

    def _current_region(self) -> Optional['StatementRegion']:
        region = None
        block = self.text

        if self.spec_start is None:
            return region

        op = self.op_expr  # aka delimiter
        subst = self.subst_expr
        spec = Region(block, self.spec_start, self.spec_end)
        expression = Region(block, self.expression_start, self.expression_end)
        start_offset = self.spec_start
        end_offset = self.expression_end

        try:
            # if op is None:
            #     region = MacroRegion(block, start_offset, end_offset, spec, expression)
            if op == ':':
                region = TestExpressionRegion(block, start_offset, end_offset, spec, expression, op, subst)
            elif op.endswith('->'):
                if op.startswith('L'):
                    region = LexiconImportRegion(block, start_offset, end_offset, spec, expression, op, subst)
                else:
                    region = PhraseExpressionRegion(block, start_offset, end_offset, spec, expression, op, subst)
            elif op == '<-':
                region = ImportRegion(block, start_offset, end_offset, spec, expression, op, subst)
                if region.is_namespace_import():
                    self.scope = region
                    self.scope_indent = None
            elif op == '~':
                region = CoordRegion(block, start_offset, end_offset, spec, expression, op, subst)
            elif op == '^':
                region = ParseExpressionRegion(block, start_offset, end_offset, spec, expression, op, subst)
            elif op == '$':
                region = FrameRegion(block, start_offset, end_offset, spec, expression, op, subst)
        except GenericException as e:
            region = BrokenRegion(block, start_offset, end_offset, str(e))

        self._reset_parse_state()

        return region

    def regions(self) -> Iterator['StatementRegion']:
        self.lines = re.split('\n', self.text)
        for reg in self._regions():
            yield reg

    def _regions(self) -> Iterator['StatementRegion']:

        self. offset = 0

        while len(self.lines) > 0:

            line = self.lines.pop(0)
            llen = len(line)
            line = re.sub(r'\s+$', '', line)
            tllen = len(line)

            def done(reset_scope=False) -> None:
                self.offset += llen + 1
                if reset_scope:
                    self.scope = None
                    self.scope_indent = None

            def broken(start, msg) -> BrokenRegion:
                return BrokenRegion(self.text, start, self.offset + tllen, brokenness=msg)

            def empty_line(ln) -> bool:
                return not re.search(r'\S', ln)

            def comment_region(ln) -> Optional[CommentRegion]:
                if re.match(r'\s*#', ln):
                    return CommentRegion(self.text, self.offset, self.offset + tllen)
                else:
                    return None

            # Empty line
            if empty_line(line):
                done()
                continue

            # Comment line
            reg = comment_region(line)
            if reg:
                yield reg
                done()
                continue

            indent_len = 0

            # Indented
            m = re.match(r'(\s+)', line)
            if m:
                indent_len = len(m.group(1))
                # We're in an indented block
                if self.scope is not None and self.scope_indent is None:
                    self.scope_indent = indent_len
                if self.scope_indent is not None:
                    if indent_len != self.scope_indent:
                        yield broken(self.offset + indent_len, "Bad indentation")
                        done(reset_scope=True)
                        continue
            else:
                self.scope = None
                self.scope_indent = None

            # New statement
            m = re.match(self.STATEMENT, line)
            if not m:
                yield broken(self.offset + indent_len, "Unparsable: %s" % line)
                done(reset_scope=(indent_len == 0))
                continue

            spec_start = self.offset + indent_len
            spec_end = self.offset + indent_len + len(m.group(1))
            op = m.group(2)  # aka delimiter
            subst = m.group(3)
            expr = m.group(4)
            expression_start = self.offset + m.start(4)
            expression_end = self.offset + m.end(4)
            # print(f"name={m.group(1)}, op={op}, subst={subst}, expr={expr}")

            self.offset += llen + 1

            # Empty import is a special case
            if not (op == '<-' and expr == ''):
                # Include any continuation lines
                while len(self.lines) > 0:
                    next_line = self.lines[0]
                    if empty_line(next_line) or comment_region(next_line):
                        break
                    m = re.match(r'(\s*)', next_line)
                    if len(m.group(1)) <= indent_len:
                        break
                    # Continuation
                    line = self.lines.pop(0)
                    llen = len(line)
                    line = re.sub(r'\s+$', '', line)
                    tllen = len(line)
                    expression_end = self.offset + tllen
                    self.offset += llen + 1

            # We now have a full expression. Yield a type-specific region for it.
            spec = Region(self.text, spec_start, spec_end)
            expression = Region(self.text, expression_start, expression_end)
            so = spec_start
            eo = expression_end
            # print(f"name={m.group(1)}, spec={spec}, expression={expression}")
            try:
                if op == ':':
                    yield TestExpressionRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                elif op.endswith('->'):
                    if op.startswith('L'):
                        yield LexiconImportRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                    else:
                        yield PhraseExpressionRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                elif op == '<-':
                    region = ImportRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                    if region.is_namespace_import():
                        self.scope = region
                        self.scope_indent = None
                    yield region
                elif op == '~':
                    yield CoordRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                elif op == '^':
                    yield ParseExpressionRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
                elif op == '$':
                    yield FrameRegion(self.text, so, eo, spec, expression, op, subst, scope=self.scope)
            except GenericException as e:
                yield BrokenRegion(self.text, so, eo, str(e))

        # end while len(self.lines) > 0

    # TODO Are we ready to delete this yet?
    r"""
    def regions_old(self):

        block = self.text
        offset = 0

        for line in re.split('\n', block):

            llen = len(line)
            line = re.sub(r'\s+$', '', line)
            tllen = len(line)

            if line.startswith('#'):
                reg = self._current_region()
                if reg is not None:
                    yield reg
                yield CommentRegion(block, offset, offset + tllen)

            # Emtpy line.  Possibly terminate a statement.
            elif not re.search(r'\S', line):
                reg = self._current_region()
                if reg is not None:
                    yield reg

            # Indented.  Either a scoped statement or a continuation
            elif re.match(r'\s', line):
                if self.scope is not None:
                    indentation = re.match(r'(\s+)', line).group(1)
                    indent_len = len(indentation)
                    if self.scope_indent is None:
                        self.scope_indent = indent_len
                    # Bad indentation
                    if indent_len < self.scope_indent:
                        reg = self._current_region()
                        if reg is not None:
                            yield reg
                        yield BrokenRegion(block, offset, offset + tllen, "Under-indented statement")
                        self._reset_parse_state(reset_scope=True)
                    # New statement
                    elif indent_len == self.scope_indent:
                        reg = self._current_region()
                        if reg is not None:
                            yield reg
                        reg = self.statement_start(block, line, offset, tllen)
                        if reg is not None:
                            yield reg
                    # Continuation
                    else:
                        if self.spec_start is None:
                            yield BrokenRegion(block, offset, offset + tllen, "Unexpected indentation")
                            self._reset_parse_state(reset_scope=True)
                        else:
                            self.expression_end = offset + tllen
                else:
                    if self.spec_start is None:
                        yield BrokenRegion(block, offset, offset + tllen, "Unexpected indentation")
                    else:
                        self.expression_end = offset + tllen

            # Statement start
            else:
                reg = self._current_region()
                if reg is not None:
                    yield reg
                self.scope = None
                reg1, reg2 = self.statement_start(block, line, offset, tllen)
                if reg1:
                    yield reg1
                if reg2:
                    yield reg2

            offset += llen + 1

        reg = self._current_region()
        if reg is not None:
            yield reg

    def statement_start(self, block, line, offset, tllen) -> Optional['BrokenRegion']:
        m = re.match(self.STATEMENT, line)
        if not m:
            self._reset_parse_state()
            return BrokenRegion(block, offset, offset + tllen)
        self.op_expr = m.group(2)
        self.subst_expr = m.group(3)
        self.spec_start = offset
        self.spec_end = offset + len(m.group(1))
        self.expression_start = offset + m.start(4)
        self.expression_end = offset + m.end(4)
        return None
    """

    def statements(self) -> Iterator['InterpretableRegion']:
        for region in self.regions():
            if isinstance(region, InterpretableRegion):
                yield region


# Statement parsing is typically driven by VRManager.parse_block(), although
# in the GUI the top level is driven by PatternPane.get_pattern_regions(),
# as the pane needs to keep track of the regions in addition to registering
# them with the top level VRManager.
#
# A StatementParser instance reads the patterns text and generates regions.
# parse_block() only cares about InterpretableRegion's, so it calls
# statements(), but get_pattern_regions() cares about all regions, 
# (base class StatementRegion, confusingly) so it calls regions().
#
# The primary call for both is region.register(), passing a VRManager.
# InterpretableRegion's CALL BACK to manager.register(), passing self.
#
# ** That is kind of confusing, but there are a few reasons for it.
# First, BrokenRegion and CommentRegion have register() be a no-op.
# Second, ExtractorRegion has to check for a local namespace (empty import) 
# manager, and register itself with that if there is one.
#
# VRManager.register() will call region.interpret(), passing self.
# That generally calls to region's _interpret().
# This create an instance of some Extractor (or a VRManager for import), 
# and sets the region's interpretation field to that.
# TODO How is that field used?
# VRManager also stores both the region and extractor.
#
# _interpret generally instantiates some kind of Expression class,
# passing the manager to it, then calls the expression's parse() method, 
# passing the rule RHS string (expression string).
# It's parse() that creates the Extractor, which _interpret returns.
# I think generally the Expression instance is dropped (not stored)
# after it performs the parsing.
# The extractor keeps a reference to the manager, so the extractor can use
# the manager to look up references to other rules the extractor references.


# Plain Region is used for the statement "spec" (LHS) and expression (RHS) 
# strings inside StatementParser.
class Region:
    """Just represents a range of text."""

    def __init__(self, text: str, start_offset: int, end_offset:int):
        self.text = text
        self.start_offset = start_offset
        self.end_offset = end_offset

    def source_string(self) -> str:
        return self.text[self.start_offset:self.end_offset]

    def __str__(self):
        text = self.source_string().replace('\n', ' ')
        return "%s(%s)" % (self.__class__, text)
        # return "<%s object at %s>(%s)" % (self.__class__.__name__, hex(id(self)), text)  # DEBUG


# This is the base class of all other Region subtypes, including BrokenRegion 
# and CommentRegion.
# The naming is a little off; StatementParser.regions() generates StatementRegions,
# while StatementParser.statements() generates InterpretableRegions.
# Also, you'd think that only an InterpretableRegion would have an 
# interpretation attribute, but the GUI code is currently checking 
# region.interpretation rather than isinstance(region, InterpretableRegion).
# The GUI code is also calling region.get_namespace(), which is only defined 
# on the InterpretableRegion subclass ExtractorRegion, so that's not ideal 
# either (and gives a compiler warning).
class StatementRegion(Region, ABC):
    """Abstract class. Key abstract method is register."""

    def __init__(self, text, start_offset, end_offset):
        super().__init__(text, start_offset, end_offset)
        self.interpretation = None  # generally an Extractor or (for imports) VRManager

    @abstractmethod
    def register(self, manager: 'VRManager') -> None:
        """Register this statement with the manager.
        This will generally call into region.interpret to create an 
        Extractor (via an Expression), and store it in the manager.
        Regions (eg broken ones) are permitted to not register themselves,
        which is why the manager doesn't directly register the region 
        with itself but calls this instead."""
        pass


class BrokenRegion(StatementRegion):

    def __init__(self, text, start_offset, end_offset, brokenness="Syntax error"):
        super().__init__(text, start_offset, end_offset)
        self.brokenness = brokenness

    def register(self, manager) -> None:
        """This implementation is a no-op."""
        pass

    
class CommentRegion(StatementRegion):

    def register(self, manager):
        """This implementation is a no-op."""
        pass


# Expression classes typically have a parse() method that returns 
# an Extractor instance.
class InterpretableRegion(StatementRegion):
    """Abstract class. Key abstract method is _interpret which generally 
    returns some kind of Extractor or similar instance via an Expression.
    For import regions, _interpret returns a VRManager for the rules 
    in the import file or local scope."""

    def __init__(self, text, start_offset, end_offset, 
                 spec_region: Region, expression_region: Region,
                 op: str, subst: str):
        super().__init__(text, start_offset, end_offset)
        self.spec_region = spec_region
        self.expression_region = expression_region
        self.op = op  # aka delimiter
        self.subst = subst

    def spec(self) -> str:
        """Returns the substring of the LHS of a statement, before the delimiter.
        Typically this is a rule name (or import name), but we call it 'spec' 
        to allow more conceptual generality."""  # eg for macros
        return self.spec_region.source_string()

    def expression(self) -> str:
        """Returns the substring of the RHS of a statement, after the delimiter.
        Note this returns a string, not a Expression instance."""
        return self.expression_region.source_string()

    def get_local_manager(self, manager: 'VRManager') -> 'VRManager':
        """This base implementation just returns the passed argument."""
        return manager

    def register(self, manager) -> None:
        manager = self.get_local_manager(manager)
        manager.register(self)

    # Could conceivably make a type alias "Interpretation" for the return 
    # value. Note FWIW that set_name gets called on each type from 
    # VRManager.register.
    def interpret(self, manager: 'VRManager') -> Union[Extractor, Regex, 'VRManager']:
        """Return region interpretation (Extractor/etc) held by region.
        If interpretation is not already set, call _interpret to create it, 
        and set its 'name' to our 'spec'."""
        if self.interpretation is None:
            # print("Interpreting", self.expression(), file=sys.stderr)
            self.interpretation = self._interpret(manager)
            # Or could pass name to _interpret?
            # TODO OTOH, this is already redundant with manager.register, 
            # which calls us.
            self.interpretation.name = self.spec()
        # else:  # not sure if this ever happens; doesn't seem to
        #     print(f"{self} interpretation already done")  # debug
        return self.interpretation

    @abstractmethod
    def _interpret(self, manager: 'VRManager') -> Union[Extractor, Regex, 'VRManager']:
        """Based on the statement RHS expression string, create an 
        Expression or similar class instance, associate it with 
        the given manager, and typically call its parse() method 
        to create an Extractor/etc, and return that.
        """
        raise NotImplementedError()

    def interpret_substitutions(self) -> Optional[Mapping[str, str]]:
        """
        Parse the substitutions (bindings) string, if any, into a dict. 
        """
        if not hasattr(self, 'subst'):
            return None
        if self.subst is None:
            return None
        m = re.match(r'\[(.*?)]', self.subst)
        if not m:
            return None
        substitutions = {}
        subst_expr = re.split(r'\s*,\s*', m.group(1))
        for s in subst_expr:
            # TODO I changed this to allow dotted name substitutions
            # on March 29, 2024 2:16 PM, but have not yet thought it
            # through or done anything to make sure this will be handled
            # downstream.
            m = re.match(r'(\w+(?:\.\w+)*)\s*=\s*(\w+(?:\.\w+)*)', s)
            # m = re.match(r'(\w+)\s*=\s*(\w+)', s)
            if not m:
                raise GenericException(msg="Malformed substitution: %s" % s)
            substitutions[m.group(1)] = m.group(2)
        return substitutions


# Unfinished. The substitution capability does most or all of what the 
# macro was intended to do.
class MacroRegion(InterpretableRegion):

    def _interpret(self, manager):
        # signature = self.spec()
        # m = re.match(r'(\w+)\((.*?)\)', signature)
        # expression = self.expression()
        raise NotImplementedError()


class ExtractorRegion(InterpretableRegion):
    """Still abstract. Allows for a statement to be associated with 
    a sub-manager for a block of statements (established by an "empty 
    import" statement) rather than with the manager for the whole file."""

    def __init__(self, text, start_offset, end_offset,
                 spec_region, expression_region, op, subst,
                 scope: 'ImportRegion' = None):
        super().__init__(text, start_offset, end_offset, spec_region, expression_region, op, subst)
        self.scope = scope

    # Extractor regions might be at top level in a rules file, 
    # or they might be in the scope of an "empty import" 
    # in which case there is a local manager for the scope, 
    # and extractors get added to that manager.
    def get_local_manager(self, manager: 'VRManager') -> 'VRManager':
        """If no local manager, return argument."""
        if self.scope is None:
            return manager
        else:
            return self.scope.namespace_manager(manager)

    def get_namespace(self) -> Optional[str]:
        """Local namespace name, if region is associated with one."""
        if self.scope is None:
            return None
        return self.scope.spec()


class TestExpressionRegion(ExtractorRegion):

    def _interpret(self, manager) -> TokenTest:
        # print(f"{self}._interpret called with {manager}")
        test = TokenTestExpression(expr=self.expression(), manager=manager).parse()
        subst = self.interpret_substitutions()
        test.set_substitutions(subst)
        return test


class PhraseExpressionRegion(ExtractorRegion):

    def _interpret(self, manager) -> Regex:
        # print(f"{self}._interpret called with {manager}")
        regex = RegexExpression(expr=self.expression(), fa_class=FiniteAutomaton, manager=manager).parse()
        regex.case_insensitive = self.op.startswith('i')
        subst = self.interpret_substitutions()
        regex.set_substitutions(subst)
        return regex


class LexiconImportRegion(PhraseExpressionRegion):
    """"Phrase lexicon" defining a single rule recognizing multiple literal 
    phrases; see VRPhraseExpressions.md."""

    # Note that here "c" stands for CSV, while in token lexicons 
    # "c" stands for (co)cluster.
    def _interpret(self, manager):
        case_insensitive = 'i' in self.op
        is_csv = False
        target_column = None
        m = re.search(r'c(\d*)', self.op)
        if m:
            is_csv = True
            if len(m.group(1)) > 0:
                target_column = int(m.group(1))
        fa = manager.import_lexicon_matcher(self.expression(), case_insensitive, is_csv, target_column)
        fa.manager = manager
        fa.set_substitutions(None)
        return fa


class ParseExpressionRegion(ExtractorRegion):

    def _interpret(self, manager) -> Regex:
        # print(f"{self}._interpret called with {manager}")
        regex = RegexExpression(expr=self.expression(), fa_class=ArcFiniteAutomaton, manager=manager).parse()
        regex.case_insensitive = self.op.startswith('i')
        subst = self.interpret_substitutions()
        regex.set_substitutions(subst)
        return regex


class ImportRegion(ExtractorRegion):

    def __init__(self, text, start_offset, end_offset,
                 spec_region, expression_region, op, subst,
                 scope: 'ImportRegion' = None):
        super().__init__(text, start_offset, end_offset, spec_region, expression_region, op, subst, scope)
        expr = self.expression()
        if re.search(r'\S', expr):
            self.namespace = False
        else:
            self.namespace = True

    def _interpret(self, manager) -> 'VRManager':
        # print(f"{self}._interpret called with {manager}")
        expr = self.expression()
        if self.namespace:
            # "empty import"
            result = manager.import_file()
        elif '{' not in expr:
            # regular import
            result = manager.import_file(expr)
        else:
            # This is an undocumented import type.
            result = manager.import_token_tests(self.spec(), expr)
        result.substitutions = None  # needed?
        return result

    def is_namespace_import(self) -> bool:
        return self.namespace

    def namespace_manager(self, manager: 'VRManager') -> 'VRManager':
        """Assuming we represent a namespace, get the sub-manager that really 
        implements it."""
        name = self.spec()
        return manager.get_import(name)


class CoordRegion(ExtractorRegion):

    def _interpret(self, manager) -> Coordinator:
        # print(f"{self}._interpret called with {manager}")
        coord = CoordinatorExpression(expr=self.expression(), manager=manager).parse()
        subst = self.interpret_substitutions()
        coord.set_substitutions(subst)
        return coord


class FrameRegion(ExtractorRegion):

    def _interpret(self, manager) -> FrameExtractor:
        # print(f"{self}._interpret called with {manager}")
        frame = FrameExpression(expr=self.expression(), manager=manager).parse()
        subst = self.interpret_substitutions()
        frame.set_substitutions(subst)
        return frame
