from math import sqrt
import plac
from nlpcore.tseqsrc import PlainDirectorySource


class Distribution:

    def __init__(self, support=None, pseudo_count=1.0):
        self.total = 0
        self.counts = {}
        self.cached_probs = {}
        self.pseudo_count = pseudo_count
        if support is None:
            self.support = set()
        else:
            self.support = support

    def observe(self, what, how_much=1.0):
        self.support.add(what)
        self.total += how_much
        try:
            self.counts[what] += how_much
        except KeyError:
            self.counts[what] = how_much

    def frequency(self, what):
        try:
            return self.counts[what]
        except KeyError:
            return 0

    def probability(self, what):
        count = self.frequency(what)
        if count in self.cached_probs:
            return self.cached_probs[count]
        prob = (self.pseudo_count + count) / (self.pseudo_count * len(self.support) + self.total)
        self.cached_probs[count] = prob
        return prob

    def hellinger_distance(self, other):
        total = 0.0
        # Throw out any zero-count terms, as they have no impact on the distance
        myterms = set(t for t in self.support if t in self.counts)
        other_terms = set(t for t in self.support if t in other.counts)
        distance_terms = myterms | other_terms
        for term in distance_terms:
            diff = sqrt(self.probability(term)) - sqrt(other.probability(term))
            total += diff * diff
        return (1.0 / sqrt(2.0)) * sqrt(total)

    def prune(self, keepers):
        dist = Distribution(support=keepers, pseudo_count=self.pseudo_count)
        for item in keepers:
            freq = self.frequency(item)
            if freq > 0:
                dist.observe(item, freq)
        return dist


class TermCooccurrence:

    def __init__(self, window=1, min_frequency=5, min_context_frequency=5, pseudo_count=1.0, verbose=False):
        """
        Define a coocurrence counter.  The window parameter specifies the desired type of coocurrence, as follows:
           N = 0: term X doc
           N > 0: adjacency
        min_frequency specifies a minimum occurrence frequency for downstream operations
        pseudo_count implements a simple form of smoothing
        """
        if window < 0:
            raise ValueError("Adjacency window must be an integer >= 0")
        self.window = window
        self.min_frequency = min_frequency
        self.min_context_frequency = min_context_frequency
        self.pseudo_count = pseudo_count
        self.verbose = verbose
        self.marginals = Distribution(pseudo_count=pseudo_count)
        self.context_support = set()
        self.pruned_cooc = {}
        self.cooc = {}
        self.distances = {}

    def count(self, tseqsrc):
        count = len(tseqsrc)
        visited = 0
        for docid, tseqs in tseqsrc.token_sequences():
            if self.window == 0:
                self._count_termdoc(docid, tseqs)
            else:
                self._count_adjacency(tseqs)
            visited += 1
            if self.verbose:
                if visited % 100 == 0:
                    print("\r%d/%d" % (visited, count), end="")
#            if visited >= 1000:
#                break
        if self.verbose:
            print("\r%d/%d" % (visited, count))

    def _count_termdoc(self, docid, tseqs):
        self.marginals.observe(docid)
        docdist = self.cooc[docid] = Distribution(support=self.context_support, pseudo_count=self.pseudo_count)
        for tseq in tseqs:
            for token in tseq:
                token = token.lower()
                docdist.observe(token)

    def _count_adjacency(self, tseqs):

        def tabulate(tokens, index, offset):
            token1 = tokens[index]
            token2 = tokens[index + offset]
            self.marginals.observe(token1)
            try:
                dist = self.cooc[token1]
            except KeyError:
                dist = self.cooc[token1] = Distribution(support=self.context_support, pseudo_count=self.pseudo_count)
            dist.observe(token2)

        w = self.window
        for tseq in tseqs:
            tokens = [ ' BOS ' for _ in range(w) ] + [ t.lower() for t in tseq ] + [ ' EOS ' for _ in range(w) ]
            for i in range(w, w + len(tseq)):
                for offs in range(-w, w+1):
                    if offs == 0:
                        continue
                    tabulate(tokens, i, offs)

    def hellinger_distance(self, term1, term2):
        dist1 = self.pruned_cooc[term1]
        dist2 = self.pruned_cooc[term2]
        return dist1.hellinger_distance(dist2)

    def _prune_cooc(self):
        if self.min_context_frequency is None:
            self.pruned_cooc = self.cooc
            return

        # Marginal distribution of contexts
        contexts = Distribution()
        for term_dist in self.cooc.values():
            for context, freq in term_dist.counts.items():
                contexts.observe(context, freq)

        keepers = set(x for x in contexts.support if contexts.counts[x] >= self.min_context_frequency)

        for term, dist in self.cooc.items():
            self.pruned_cooc[term] = dist.prune(keepers)

    def distance_table(self, max_entries=100):

        if self.verbose:
            print("Computing distances for %d terms" % len(self.marginals.support))

        self._prune_cooc()

        freqs = ((t, self.marginals.frequency(t)) for t in self.marginals.support)
        freqs = dict((t, f) for t, f in freqs if f > self.min_frequency)
        terms = list(sorted(freqs.keys(), key=lambda t: freqs[t], reverse=True))
        tcount = len(terms)
        table = {}

        def tally(i, j, distance):
            try:
                tab = table[i]
            except KeyError:
                tab = table[i] = {}
            tab[j] = distance

        for i in range(len(terms) - 1):
            distances = [self.hellinger_distance(terms[i], terms[j]) for j in range(i+1, len(terms))]
            for j, distance in enumerate(distances):
                tally(i, i + j + 1, distance)
                tally(i + j + 1, i, distance)
            if self.verbose:
                if i % 1 == 0:
                    print("\r%d/%d" % (i, tcount), end="")
        if self.verbose:
            print("\r%d/%d" % (tcount, tcount))

        result = {}

        for i, tab in table.items():
            term = terms[i]
            closest = list(sorted(((terms[j], d) for j, d in tab.items()), key=lambda x: x[1], reverse=True))
            if len(closest) > max_entries:
                closest = closest[0:max_entries]
            result[term] = dict(closest)

        return terms, result


if __name__ == '__main__':

    def main(indir, outdir, window=1):
        source = PlainDirectorySource(indir)
        cooc = TermCooccurrence(window=window, verbose=True, min_frequency=20)
        print("Tabulating")
        cooc.count(source)
        print("Creating distance table")
        terms, table = cooc.distance_table()
        termmap = dict((terms[i], i) for i in range(len(terms)))
        with open("%s/xLabels.tsv" % outdir, "w") as fh:
            for term in terms:
                print(term, file=fh)
        with open("%s/xxAssocAdj.tsv" % outdir, "w") as fh:
            for term in terms:
                termi = termmap[term]
                term_table = table[term]
                for other_term, distance in term_table.items():
                    other_termi = termmap[other_term]
                    print("%d\t%d\t%f" % (termi, other_termi, distance), file=fh)

    plac.call(main)




