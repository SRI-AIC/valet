import unittest

from valetrules.match import FAMatch, FAArcMatch, CoordMatch
from valetrules.test.valet_test import ValetTest


def Dont_setUpModule():  # DEBUG, disabled
    import logging.config
    from nlpcore.logging import no_datetime_config
    logging.config.dictConfig(no_datetime_config)


class TestParse(ValetTest):

    # RVS: I've seen enough anomalies to know that we badly need a set of
    # simple boundary condition tests.
    # For these, we might want to bypass the spacy/stanza parsing and 
    # manually generate parses for simple basic situations.
    # We might also want to test lower level methods.
    def test_new(self):
        # I think that a rule that does something sort of like
        # rule ^ &any &any might be sufficient to ... maybe not.
        # Probably need &x1 &x2 so we can check for order.
        # Possibly part of the problem is that we have not defined
        # the meaning of arguments precisely enough. E.g.,
        # "Generate all matches falling within indicated bounds."
        # That refers to the start/end args (not the bounds arg),
        # but the main issue is what "falling within start/end" means, 
        # in this and all related contexts.
        pass

    # Test to contrast the behavior here with the same-named test in
    # test_phrase.py.
    # In particular, note that here it generates *multiple* matches within 
    # "Western Great Basin Areas" (which have inclusive end index), while 
    # there it generates a *single* match (which has exclusive end index).
    # "Rocky Mountain" and "Western Great Basin Areas" are runs of both 
    # consecutive &nnp tokens and of "compound" edges (though just a length 1 
    # run of compound for "Rocky Mountain").
    def test_match_generation(self):
        print("test_match_generation")
        # It's not normally a good idea to have two + in a row with 
        # the same test or extractor, but do so to test the behavior.
        patterns = """
compounds1 ^ compound+
compounds2 ^ compound+ compound+
        """
        self.parse_block(patterns)
        # self.vrm.lookup_extractor("compounds2")[0].dump()

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'compounds2')
        matches2 = self.matches_tseq('compounds2', tseq)
        matches = matches2
        # print([str(match) for match in matches])
        self.assertEqual(len(matches), 14)
        # matches = set(matches)
        # print([str(match) for match in matches])
        # TODO Hm, why is it giving us this first match? Seems wrong.
        # It probably has to do with traversing an edge in both directions. 
        # Not entirely sure what the desired behavior should be, 
        # but this match was unexpected to me.
        # I guess that applies equally to the (8,9), (9,10), and (10,11)
        # matches.
        # See also test_edge_case_3 below.
        self.assertTrue(FAArcMatch(seq=tseq, begin=5, end=6) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=11) in matches)
        # We now also return the reversed indices matches.
        self.assertTrue(FAArcMatch(seq=tseq, begin=6, end=5) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=10) in matches)

        # Added this to see whether this variation of the rule behaves 
        # the same way or not. It does.
        # self.vrm.lookup_extractor("compounds1")[0].dump()
        matches1 = self.matches_tseq('compounds1', tseq)
        self.assertEqual(set(matches1), set(matches2))

        print("test_match_generation done")

    # Like test_match_generation but with reference tokentests.
    def test_tokentest_references(self):
        print("test_tokentest_references")
        patterns = """
compound_tt : {compound}
compound_tt_ref : &compound_tt
compounds1 ^ &compound_tt_ref+
compounds2 ^ &compound_tt_ref+ &compound_tt_ref+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'compounds2')
        matches2 = self.matches_tseq('compounds2', tseq)
        matches = matches2
        self.assertEqual(len(matches), 14)
        self.assertTrue(FAArcMatch(seq=tseq, begin=5, end=6) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=11) in matches)
        # We now also return the reversed indices matches.
        self.assertTrue(FAArcMatch(seq=tseq, begin=6, end=5) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=10) in matches)

        matches1 = self.matches_tseq('compounds1', tseq)
        self.assertEqual(set(matches1), set(matches2))

        print("test_tokentest_references done")

    def test_tokentest_references_with_substitutions(self):
        print("test_tokentest_references_with_substitutions")
        patterns = """
compound_tt : {compound}
compound_tt_alt : {compound}
compound_tt_ref : &compound_tt
compounds1 ^[compound_tt=compound_tt_alt] &compound_tt_ref+
compounds2 ^[compound_tt=compound_tt_alt] &compound_tt_ref+ &compound_tt_ref+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'compounds2')
        matches2 = self.matches_tseq('compounds2', tseq)
        matches = matches2
        self.assertEqual(len(matches), 14)
        self.assertTrue(FAArcMatch(seq=tseq, begin=5, end=6) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=8, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=10) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=11) in matches)
        # We now also return the reversed indices matches.
        self.assertTrue(FAArcMatch(seq=tseq, begin=6, end=5) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=8) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=10, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=9) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=10) in matches)

        matches1 = self.matches_tseq('compounds1', tseq)
        self.assertEqual(set(matches1), set(matches2))

        print("test_tokentest_references_with_substitutions done")

    def test_directional_modifiers_on_literals(self):
        patterns = r"""
bi   ^ nsubj dobj
dir1 ^ /nsubj \dobj
dir2 ^ \nsubj /dobj
rev  ^ dobj nsubj
dir3 ^ /dobj \nsubj
dir4 ^ \dobj /nsubj
        """
        self.parse_block(patterns)
        # - bought VBD ROOT
        #   - Rita NNP nsubj
        #   - apple NN dobj
        #     - an DT det
        text = "Rita bought an apple"

        # Note that this only matches in one direction; len(matches) = 1.
        # While you can traverse the nsubj link in the opposite of the 
        # intended direction, that leaves you at a different node (Rita) 
        # than intended (bought), and there's no edge with the next label 
        # from that unintended node.
        # test_match_generation has matches in both directions only because 
        # its rule's edge sequence is symmetric.
        tseq = self.tseq_from_text(text, 'bi')
        matches = self.matches_tseq('bi', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=3) in matches)

        matches = self.matches_tseq('dir1', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=3) in matches)

        matches = self.matches_tseq('dir2', tseq)
        self.assertEqual(len(matches), 0)

        matches = self.matches_tseq('rev', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=0) in matches)

        matches = self.matches_tseq('dir3', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=0) in matches)

        matches = self.matches_tseq('dir4', tseq)
        self.assertEqual(len(matches), 0)

    # Test is almost identical to above.
    #
    # valetrules.regex.RegexExpression's ctor's default token_expression 
    # indicates that directional modifiers are allowed in token test 
    # references in parse (and phrase) expressions. 
    # Trying to verify how that works.
    # I'm guessing it doesn't make sense to use them with phrase expressions, 
    # but I think the same code is used for both, so they'd perhaps parse OK?
    # 
    # I found it a little unintuitive that the & comes BEFORE the /\; 
    # I would have expected the opposite. 
    # But I guess it was probably the most convenient for Dayne, 
    # at least given the way the rest of the code works.
    def test_directional_modifiers_on_token_tests(self):
        patterns = r"""
nsubj : { nsubj }
dobj  : { dobj }
bi   ^ &nsubj &dobj
dir1 ^ &/nsubj &\dobj
dir2 ^ &\nsubj &/dobj
rev  ^ &dobj &nsubj
dir3 ^ &/dobj &\nsubj
dir4 ^ &\dobj &/nsubj
        """
        self.parse_block(patterns)
        text = "Rita bought an apple"
        tseq = self.tseq_from_text(text, 'bi')

        matches = self.matches_tseq('bi', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=3) in matches)

        matches = self.matches_tseq('dir1', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=3) in matches)

        matches = self.matches_tseq('dir2', tseq)
        self.assertEqual(len(matches), 0)

        matches = self.matches_tseq('rev', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=0) in matches)

        matches = self.matches_tseq('dir3', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=0) in matches)

        matches = self.matches_tseq('dir4', tseq)
        self.assertEqual(len(matches), 0)

    # Originally there was unexpected behavior here, but after some 
    # code changes it is now working as would be expected and desired.
    def test_edge_case_1(self):
        # The reason I had @cc on the RHS of conj1 instead of a literal cc 
        # is that I wanted to be able to select on it, and parse patterns  
        # currently don't record token test submatches.
        # However, there's really no point in selecting something that's 
        # already known to have the value "cc".
        patterns = r"""
cc_tt : { cc }
cc    ^ &cc_tt
conjs ^ conj+
conj1 ^ @cc conj
conj2 ~ select(cc, conj1)
conj0 ^ @cc
conj3 ~ select(cc, conj0)
        """
        self.parse_block(patterns)
        text = "Can I have a cheeseburger with no pickles, onions, or ketchup?"
        tseq = self.tseq_from_text(text, 'cc')

        matches = list(self.matches_tseq('cc', tseq))
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=9) in matches)

        matches = list(self.matches_tseq('conj0', tseq))
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAArcMatch(seq=tseq, begin=9, end=11) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=9) in matches)

        matches = list(self.matches_tseq('conj3', tseq))
        self.assertEqual(len(matches), 2)
        # These have different cc submatches. Could test that too.
        self.assertEqual(FAMatch(seq=tseq, begin=9, end=12), matches[0])
        self.assertEqual(FAMatch(seq=tseq, begin=9, end=12), matches[1])

        matches = list(self.matches_tseq('conj1', tseq))
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=12) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=11, end=7) in matches)

        matches = list(self.matches_tseq('conj2', tseq))
        self.assertEqual(len(matches), 2)
        # These have identical cc submatches. Could test that too.
        self.assertEqual(FAMatch(seq=tseq, begin=9, end=12), matches[0])
        self.assertEqual(FAMatch(seq=tseq, begin=9, end=12), matches[1])

    def test_edge_case_2(self):
        patterns = r"""
amod ^ amod
wrapper ^ @amod
        """
        self.parse_block(patterns)
        text = "The big fat cat is on the mat."
        tseq = self.tseq_from_text(text, 'amod')

        # I was concerned that in one or both of these rules, 
        # we'd find paths from big and fat upward to cat, 
        # but we might have trouble finding both 
        # paths from cat downward to big and fat.
        # However, both rules seem to work fine.

        matches = list(self.matches_tseq('amod', tseq))
        self.assertEqual(len(matches), 4)
        self.assertTrue(FAArcMatch(seq=tseq, begin=1, end=3) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=2, end=3) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=1) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=2) in matches)

        matches = list(self.matches_tseq('wrapper', tseq))
        self.assertEqual(len(matches), 4)
        self.assertTrue(FAArcMatch(seq=tseq, begin=1, end=3) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=2, end=3) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=1) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=3, end=2) in matches)


    # The rule here was not what I originally meant to write, 
    # but this erroneous rule happened to illustrate a bug, 
    # which is similar to the one in test_match_generation.
    def test_edge_case_3(self):
        patterns = r"""
svos_bad ^ nsubj xcomp ? dobj+
        """
        self.parse_block(patterns)
        text = "Rita wanted to buy an apple, an orange, and a pear."
        tseq = self.tseq_from_text(text, 'svos_bad')

        matches = list(self.matches_tseq('svos_bad', tseq))
        self.assertEqual(len(matches), 2)
        # TODO This match is wrong. It appears the dobj edge gets traversed twice?
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=3) in matches)
        self.assertTrue(FAArcMatch(seq=tseq, begin=0, end=5) in matches)


if __name__ == '__main__':
    print("test_parse.py starting")
    unittest.main()
    print("test_parse.py finished")
