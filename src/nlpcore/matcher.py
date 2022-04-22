import re

# A holder class that manages a set of named extractors and supports Boolean combinations


class Matcher:

    def __init__(self, worker_class):
        self.worker_class = worker_class
        self.atom_re = worker_class.atom_re()
        self.matchers = {}

    def parse_file(self, fname):
        with open(fname) as fh:
            contents = fh.read()
            self.parse_block(contents)

    def parse_block(self, block):
        for statement in self._block_statements(block):
            self.parse_statement(statement)

    def parse_statement(self, statement):
        m = re.match(r'(\w+)\s*:\s*(\S.*)', statement)
        if not m:
            raise ValueError("Mal-formed statement: %s" % statement)
        name = m.group(1)
        expression = m.group(2)
        matcher = self.parse_expression(expression)
        self.matchers[name] = matcher

    def parse_expression(self, expression):
        self.tokenize_expression(expression)
        return self.or_expression()

    def or_expression(self):
        result = [self.and_expression()]
        while self.next_token_matches('or', False):
            result.append(self.and_expression())
        if len(result) == 1:
            return result[0]
        else:
            return OrMatcher(*result)

    def and_expression(self):
        result = [self.not_expression()]
        while self.next_token_matches('and', False):
            result.append(self.not_expression())
        if len(result) == 1:
            return result[0]
        else:
            return AndMatcher(*result)

    def not_expression(self):
        negated = False
        if self.next_token_matches('not'):
            negated = True
            self.shift_token('not')
        atom = self.atom_expression()
        if negated:
            return NotMatcher(atom)
        else:
            return atom

    def atom_expression(self):
        if self.next_token_matches('('):
            self.shift_token('(')
            result = self.or_expression()
            self.shift_token(')')
        else:
            result = self.worker_class.from_expression(self.shift_token(self.atom_re))
        return result

    def tokenize_expression(self, expression):
        token_re = r"%s|\(|\)|and|or|not" % self.atom_re
        self.tokens = re.findall(token_re, expression)

    def shift_token(self, what):
        if not self.next_token_matches(what):
            raise ValueError("Next token (%s) does not match %s" % (self.tokens[0], what))
        return self.tokens.pop(0)

    def next_token_matches(self, what, require_tokens=True):
        if len(self.tokens) == 0:
            if not require_tokens:
                return False
            if isinstance(what, str):
                raise ValueError("Expected '%s', but input is empty" % what)
            else:
                raise ValueError("Expected an operator token, but input is empty")
        token = self.tokens[0]
        if isinstance(what, str):
            return token == what
        else:
            return re.match(what, token)

    def _block_statements(self, block):

        statement = None

        for line in re.split(r'\n', block):

            line = re.sub(r'\s+$', '', line)

            # Comment or empty line
            if line.startswith('#') or not re.search(r'\S', line):
                if statement is not None:
                    yield statement
                statement = None

            # Indented.  Continuation
            elif re.match(r'\s', line):
                if statement is None:
                    raise ValueError("Stray indented line: %s" % line)
                statement += ' ' + line

            # Statement start
            else:
                if statement is not None:
                    yield statement
                statement = line

        if statement is not None:
            yield statement


class OrMatcher:

    def __init__(self, *args):
        self.elements = args


class AndMatcher:

    def __init__(self, *args):
        self.elements = args


class NotMatcher:

    def __init__(self, element):
        self.element = element
