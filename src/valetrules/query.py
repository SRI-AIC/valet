"""
Documentation TBD.
This is not a central part of the Valet code.
It is not exercised by any tests.
It doesn't seem to be referenced by any scripts, even old ones.
It is referenced by tokentest.py, but there seem to be 
no calls to the referencing methods anywhere.
"""

# TODO What's this about?


class Query(object):

    def query_string(self):
        raise NotImplementedError()

class WordQuery(Query):

    def __init__(self, word):
        self.word = word

    def query_string(self):
        return self.word

class OneOfQuery(Query):

    def __init__(self, seq):
        self.items = dict((x, 1) for x in seq)

    def query_string(self):
        return '(' + ' OR '.join(self.item.keys()) + ')'

class AndQuery(Query):

    def __init__(self, qs):
        self.qs = qs

    def query_string(self):
        return '(' + ' AND '.join((q.query_string() for q in self.qs))


class OrQuery(Query):

    def __init__(self, qs):
        self.qs = qs

    def query_string(self):
        return '(' + ' OR '.join((q.query_string() for q in self.qs))


class NotQuery(Query):

    def __init__(self, q):
        self.q = q

    def query_string(self):
        return '(NOT %s)' % self.q.query_string()
