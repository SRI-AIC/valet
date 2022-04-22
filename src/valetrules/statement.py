import re

from .tokentest import TokenTestExpression
from .regex import RegexExpression
from .fa import FiniteAutomaton, ArcFiniteAutomaton
from .coordinatorexp import CoordinatorExpression
from .frame import FrameExpression

from nlpcore.dbfutil import GenericException

"""
Provides the StatementParser class, which takes a text string with 
definitions in the VR pattern language, and parses it into regions 
representing individual definitions. 

Each region is represented by a StatementRegion class or subclass instance.
Subclasses include BrokenRegion, CommentRegion, TestExpressionRegion, 
PhraseExpressionRegion, DependencyRegion, CoordRegion, FrameRegion, etc.

Region classes are associated with a similar (but not identical) taxonomy 
of expression classes typically defined in individual modules including 
tokentest, coordinatorexp, frame, etc.
"""


class StatementParser(object):

    spec_start = None
    spec_end = None
    expression_start = None
    expression_end = None
    op_expr = None

    def __init__(self, text):
        self.text = text

    def _reset_parse_state(self):
        self.spec_start = None
        self.spec_end = None
        self.expression_start = None
        self.expression_end = None
        self.op_expr = None

    def _current_region(self):
        region = None
        block = self.text

        if self.spec_start is None:
            return region

        op = self.op_expr
        spec = StatementRegion(block, self.spec_start, self.spec_end)
        expression = StatementRegion(block, self.expression_start, self.expression_end)
        start_offset = self.spec_start
        end_offset = self.expression_end

        try:
            if op is None:
                region = MacroRegion(block, start_offset, end_offset, spec, expression)
            elif op == ':':
                region = TestExpressionRegion(block, start_offset, end_offset, spec, expression, op)
            elif op.endswith('->'):
                if op.startswith('L'):
                    region = LexiconImportRegion(block, start_offset, end_offset, spec, expression, op)
                else:
                    region = PhraseExpressionRegion(block, start_offset, end_offset, spec, expression, op)
            elif op == '<-':
                region = ImportRegion(block, start_offset, end_offset, spec, expression, op)
            elif op == '~':
                region = CoordRegion(block, start_offset, end_offset, spec, expression, op)
            elif op == '^':
                region = DependencyRegion(block, start_offset, end_offset, spec, expression, op)
            elif op == '$':
                region = FrameRegion(block, start_offset, end_offset, spec, expression, op)
        except GenericException:
            region = BrokenRegion(block, start_offset, end_offset)

        self._reset_parse_state()
        return region

    def regions(self):

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

            # Indented.  Continuation
            elif re.match(r'\s', line):
                if self.spec_start is None:
                    yield BrokenRegion(block, offset, offset + tllen)
                else:
                    self.expression_end = offset + tllen

            # Statement start
            else:
                reg = self._current_region()
                if reg is not None:
                    yield reg
                # Macro
                m = re.match(r'(\w+\(.*?\))\s*=\s*(.*)', line)
                if m:
                    self.op_expr = None
                    self.spec_start = offset
                    self.spec_end = offset + m.end(1)
                    self.expression_start = offset + m.start(2)
                    self.expression_end = offset + m.end(2)
                else:
                    # Regular statement
                    m = re.match(r'(\w+)\s*(i?->|L[ic\d]*->|:|<-|~|\^|\$)\s*(.*)', line)
                    if m:
                        self.op_expr = m.group(2)
                        self.spec_start = offset
                        self.spec_end = offset + len(m.group(1))
                        self.expression_start = offset + m.start(3)
                        self.expression_end = offset + m.end(3)
                    else:
                        yield BrokenRegion(block, offset, offset + tllen)

            offset += llen + 1

        reg = self._current_region()
        if reg is not None:
            yield reg

    def statements(self):
        for region in self.regions():
            if isinstance(region, InterpretableRegion):
                yield region


class StatementRegion(object):

    spec_start = None
    spec_end = None
    expression_start = None
    expression_end = None
    op_expr = None

    def __init__(self, text, start_offset, end_offset):
        self.text = text
        self.start_offset = start_offset
        self.end_offset = end_offset

    def register(self, manager):
        raise NotImplementedError()

    def source_string(self):
        return self.text[self.start_offset:self.end_offset]


class BrokenRegion(StatementRegion):

    def register(self, manager):
        pass

    
class CommentRegion(StatementRegion):

    def register(self, manager):
        pass


class InterpretableRegion(StatementRegion):

    def __init__(self, text, start_offset, end_offset, spec_region, expression_region):
        super().__init__(text, start_offset, end_offset)
        self.spec_region = spec_region
        self.expression_region = expression_region
        self.interpretation = None

    def register(self, manager):
        manager.register(self)

    def interpret(self, manager):
        if self.interpretation is None:
            self.interpretation = self._interpret(manager)
            self.interpretation.name = self.spec()
        return self.interpretation

    def _interpret(self, manager):
        raise NotImplementedError()

    def spec(self):
        return self.spec_region.source_string()

    def expression(self):
        return self.expression_region.source_string()


class MacroRegion(InterpretableRegion):

    def _interpret(self, manager):
        signature = self.spec()
        m = re.match(r'(\w+)\((.*?)\)', signature)

        expression = self.expression()


class ExtractorRegion(InterpretableRegion):

    def __init__(self, text, start_offset, end_offset, name_region, expression_region, op):
        super().__init__(text, start_offset, end_offset, name_region, expression_region)
        self.op = op

    def _interpret(self, manager):
        raise NotImplementedError()


class TestExpressionRegion(ExtractorRegion):

    def _interpret(self, manager):
        return TokenTestExpression(manager=manager).parse(self.expression())


class PhraseExpressionRegion(ExtractorRegion):

    def _interpret(self, manager):
        regex = RegexExpression(string=self.expression(), class_=FiniteAutomaton, manager=manager).parse()
        #fa.parent = manager
        regex.fa_case_insensitive = self.op.startswith('i')
        return regex


class LexiconImportRegion(PhraseExpressionRegion):

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
        fa.parent = manager
        return fa


class ImportRegion(ExtractorRegion):

    def _interpret(self, manager):
        expr = self.expression()
        if '{' not in expr:
            return manager.import_file(expr)
        else:
            return manager.import_token_tests(self.spec(), expr)


class CoordRegion(ExtractorRegion):

    def _interpret(self, manager):
        return CoordinatorExpression(parent=manager, string=self.expression()).parse()


class DependencyRegion(ExtractorRegion):

    def _interpret(self, manager):
        regex = RegexExpression(string=self.expression(), class_=ArcFiniteAutomaton, manager=manager).parse()
        regex.fa_case_insensitive = self.op.startswith('i')
        #fa.parent = manager
        return regex


class FrameRegion(ExtractorRegion):

    def _interpret(self, manager):
        return FrameExpression(parent=manager, string=self.expression()).parse()



