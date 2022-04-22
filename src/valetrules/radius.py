from nlpcore.term_expansion import TermExpansion


class TermRadius:

    def __init__(self, expander: TermExpansion, radius: float, terms=None, match_any=True):
        self.expander = expander
        self.radius = radius
        self.match_any = match_any
        self.anchors = set()
        if terms is not None:
            for term in terms:
                self.add_term(term)

    def add_term(self, term):
        term_index = self.expander.get_term_index_from_term(term)
        self.anchors.add(term_index)

    def encloses(self, term):
        try:
            term_index = self.expander.get_term_index_from_term(term)
        except ValueError:
            # No entry for this term
            return False
        if term_index in self.anchors:
            return True
        if self.match_any:
            return any(self.expander.get_term_to_term_divergence(ti, term_index) < self.radius
                       for ti in self.anchors)
        else:
            return all(self.expander.get_term_to_term_divergence(ti, term_index) < self.radius
                       for ti in self.anchors)




