import plac
import sys
import os
import os.path
# TODO Really? Surely there's a better way?
sys.path.append(os.path.dirname("."))
from nlpcore.coclustering import SingleCoclustering
import logging
import sys


_logger = logging.getLogger(__name__)


# TODO? Should perhaps hold a coclustering field rather than inheriting?
class TermExpansion(SingleCoclustering):

    def __init__(self, input_directory):
        """
        Parameters
        ----------
        input_directory - path to the co-clustering files 
            where artifacts such as xLabels.tsv and xxAssoc.tsv live
        """
        super().__init__(input_directory)


    def read_term_expansion_data(self):
        """
        Calls a read function for the co-occurrence data necessary to support
        term expansion. Note that this is a much reduced set of data compared
        to all that is available (see the read methods in the Co-clustering
        base class for details).
        Since we are working with a minimal set of data, some available methods
        in the underlying class will not work.
        """
        
        # - self.x_labels is dictionary that maps from a term_index to its term label. (x_labels)
        # For example self.x_labels[0] = 'dog'
        self.x_labels = self.read_x_labels()

        # - self.x_to_x_divergence is a dictionary from a tuple of term
        # indices to their relative divergence, or distance, from each other.
        self.x_to_x_divergence = self.read_xx_assoc()


    def get_similar_terms(self, term, limit=20):
        """
        Get tuples of term_indices to divergence with the specified term,
        sorted by closest first. Note this will compare the specified term
        to *all* terms, not only those that are in the same term_cluster.

        Parameters
        ----------
        term : string
            the term that we want to get the closest terms for
        limit : int
            the number of terms to return. Default is 20

        Returns
        -------
        list of tuples of terms to divergence with the specified term,
        sorted by closest first. Term count returned is limited
        by the 'limit' parameter.
        """

        term_index = self.get_x_index_from_x_label(term)
        similar_term_indices = self.get_closest_xs_sorted_by_divergence(term_index, limit)
        similar_terms = []
        for x_index, divergence in similar_term_indices:
            # Calling code is not going to want to know about term indices
            # and the like so return the string instead of the index here.
            term_string = self.get_x_labels()[x_index]
            similar_terms.append((term_string, divergence))
        return similar_terms


    def get_term_index_from_term(self, term):
        """
        Convenience function that returns the term_index for the provided term

        Parameters
        ----------
        term : string
            The term string that we want to get the term_index for

        Returns
        -------
        The term_index for the provided term
        """

        return self.get_x_index_from_x_label(term)


    def get_term_to_term_divergence(self, term1, term2):
        """
        Get the divergence measure (distance) between the two specified term indices

        Parameters
        ----------
        term1 : int
            index of the first term to get the divergence measure for
        term2 : int
            index of the second term to get the divergence measure for

        Returns
        -------
        The divergence measure (distance) between the two
        specified term indices. The divergence map may have been pruned,
        leaving open the possibility that no divergence is recorded for a
        given pair of terms.  In that case, return a very high divergence.
        """

        return self.get_x_to_x_divergence(term1, term2)


# TODO Developer only,
# but I'll leave it here for now.
if __name__ == "__main__":

    def main(input_directory: "location of the co-clustering data"):
        """
        Main entry point to the Term Expansion class

        Parameters
        ----------
        input_directory : string
            location of the co_clustering data
        """
        TermExpansion(input_directory)

    plac.call(main)
