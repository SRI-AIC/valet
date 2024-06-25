import re


# AFAIK this is unfinished.
class Macro(object):

    ARGUMENT_PATTERN = r'^\w+$'

    def __init__(self, name, arg_expr, expansion_expr):
        self.name = name
        self.pattern = r'%s\s*\((.*?)\)' % name
        self.params = []
        self.expansion = None
        self.parse(arg_expr, expansion_expr)

    def parse(self, arg_expr, expansion_expr):
        for arg in re.split(r'\s*,\s*', arg_expr):
            if not re.match(self.ARGUMENT_PATTERN, arg):
                raise ValueError("Malformed macro argument: %s" % arg)
            if arg not in expansion_expr:
                raise ValueError("Macro argument '%s' does not appear in expansion (%s)" % (arg, expansion_expr))
            self.params.append(arg)
        expansion = expansion_expr
        for arg in self.params:
            expansion = expansion.replace(arg, "{%s}" % arg)
        self.expansion = expansion

    def expand(self, string):
        
        def expand_match(m):
            arg_expr = m.group(1)
            args = re.split(r'\s*,\s*', arg_expr)
            if len(args) != len(self.params):
                raise ValueError("Wrong number of arguments in macro call '%s(%s)'" % (self.name, arg_expr))
            fargs = dict(zip(self.params, args))
            return self.expansion.format(**fargs)

        return re.sub(self.pattern, expand_match, string)




