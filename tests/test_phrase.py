import unittest

from valetrules.match import FAMatch
from valetrules.test.valet_test import ValetTest
from tests.text import TEST_TEXT, ROOT_TEXT


class TestPhrase(ValetTest):

    # The next several tests are instructive
    # to step through and also serve as sort of base case tests.

    def test_token_test_submatches_of_phrase_expressions_are_recorded(self):
        print("test_token_test_submatches_of_phrase_expressions_are_recorded")
        patterns = """
tt1   : { a }
phr1 -> &tt1
        """
        self.parse_block(patterns)

        text = "a b a"
        tseq = self.tseq_from_text(text)
        matches = self.matches_tseq('phr1', tseq)
        # ['FAMatch([phr1],0,1,a, ss=[FAMatch([tt1],0,1,a)])', 'FAMatch([phr1],2,3,a, ss=[FAMatch([tt1],2,3,a)])']
        # print([str(m) for m in matches])
        assert len(matches) == 2
        for i in range(2):
            assert len(matches[i].submatches) == 1
            assert matches[i].submatches[0].name == "tt1"
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=2, end=3) in matches)
        print("test_token_test_submatches_of_phrase_expressions_are_recorded done")


    # Stepping through this shows that while a match of each disjunct is found
    # internally, both are the same length (one token), so one is chosen
    # arbitrarily.
    # Each match has one submatch, of either tt1 or tt2, but the submatches
    # are NOT COMBINED at all in the returned match; instead, one of the
    # longest matches is simply returned.
    def test_submatches_from_phrase_disjuncts_are_not_combined(self):
        print("test_submatches_from_phrase_disjuncts_are_not_combined")
        patterns = """
tt1   : /^a/
tt2   : /c$/
phr1 -> &tt1 | &tt2
        """
        self.parse_block(patterns)

        text = "abc"
        matches = self.matches('phr1', text)
        sm_names = set()
        assert len(matches) == 1
        assert len(matches[0].submatches) == 1
        assert matches[0].submatches[0].name in {"tt1", "tt2"}



    # The extractor instance here is an OrTest, not a FA.
    def test_boolean_disjuncts(self):
        print("test_boolean_disjuncts")
        patterns = """
tt1   : /^a/
tt2   : /c$/
tt3   :  &tt1 or &tt2
        """
        self.parse_block(patterns)

        text = "abc"
        matches = self.matches('tt3', text)
        print([str(m) for m in matches])
        # sm_names = set()
        assert len(matches) == 1
        assert len(matches[0].submatches) == 0
        # assert matches[0].submatches[0].name in {"tt1", "tt2"}
        print("test_boolean_disjuncts done")


    def test_phrase_disjunction_length_1(self):
        print("test_phrase_disjunction_length_1")

        patterns = """
p1 -> a | b | c
        """
        self.parse_block(patterns)

        text = "a b c d"
        matches = self.matches('p1', text)
        self.assertEqual(len(matches), 3)
        # print([str(m) for m in matches])
        # self.assertTrue(FAMatch(begin=0, end=3) in matches)

        print("test_phrase_disjunction_length_1 done")


    # This gives basically the same results as for phrases,
    # but if these were references to named token tests
    # instead of token test literals, submatches would not
    # be recorded here but would be for phrases.
    def test_tokentest_disjunction_length_1(self):
        print("test_tokentest_disjunction_length_1")

        patterns = """
t1 : { a } or { b } or { c }
        """
        self.parse_block(patterns)

        text = "a b c d"
        matches = self.matches('t1', text)
        self.assertEqual(len(matches), 3)
        # print([str(m) for m in matches])
        # self.assertTrue(FAMatch(begin=0, end=3) in matches)

        print("test_tokentest_disjunction_length_1 done")


    # I'd had some confusion about whether phrase disjunction can short-circuit.
    # It does NOT.
    # The places I know of that CAN are boolean expressions and filter
    # coordinators.
    def test_phrase_disjunction_different_lengths_returns_longest(self):
        print("test_phrase_disjunction_different_lengths_returns_longest")

        patterns = """
p1 -> a | a b | a b c
        """
        self.parse_block(patterns)

        text = "a b c d"
        tseq = self.tseq_from_text(text)
        matches = self.matches_tseq('p1', tseq)
        self.assertEqual(len(matches), 1)  # longest match is chosen
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=3) in matches)

        print("test_phrase_disjunction_different_lengths_returns_longest done")


    # This illustrates some O(N^3) behavior (here N = length of match).
    # This is O(N^3) because there are O(N^2) shorter matches (one for 
    # each start/end pair) that get dropped, and they average having 
    # O(N) submatches each.
    # TODO? It would be nice if we could at least share the submatch
    # instances rather than having to create multiple identical ones,
    # but that's probably not easy to achieve.
    # This also illustrates how the submatches are added in reverse order
    # as the recursion in the FA code is unwound.
    def test_order_n_cubed_behavior_of_runs_of_matches(self):
        print("test_order_n_cubed_behavior_of_runs_of_matches")
        patterns = """
any   : /./
phr1 -> &any +
        """
        self.parse_block(patterns)

        text = "a b a"
        matches = self.matches('phr1', text)
        # I'd like to count the shorter matches that are dropped as well
        # and assert on that to show that there are O(N^2) of them, but 
        # since they're dropped I don't have access to them to count them.
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 3)
        # ['FAMatch([phr1],0,3,a b a, ss=[FAMatch([any],2,3,a), FAMatch([any],1,2,b), FAMatch([any],0,1,a)])']
        # print([str(m) for m in matches])
        print("test_order_n_cubed_behavior_of_runs_of_matches done")


    # I suspect one major issue with John's OPS5G SRL rules
    # is that strings of (phrase '|', not boolean 'or') disjunction matches 
    # where multiple disjuncts can match is quite expensive, perhaps even 
    # exponentially so.
    #
    # This doesn't quite reproduce the situation of John's rules, though.
    # TODO I want a situation where multiple disjuncts can match a token.
    # Here the disjuncts are mutually exclusive.
    @unittest.skip("debug")
    def test_disjunction_series_1(self):
        print("test_disjunction_series_1")

        patterns = """
p1 -> a | b | c | d
p2 -> @p1+
        """
        self.parse_block(patterns)

        text2 = "1 a b 2"
        text3 = "1 a b c 2"
        text4 = "1 a b c d 2"
        for i, text in enumerate([text2, text3, text4], start=2):
            print(i)
            matches = self.matches('p2', text)
            print(len(matches))
            for m in matches:
                print(m)
            print()

        print("test_disjunction_series_1 done")


    # Contrast the behavior here with the same-named test in test_parse.py.
    # With phrase expressions we return only the longest match, and the first 
    # of those (though order is unspecified) if there are multiple.
    def test_match_generation(self):
        print("test_match_generation")
        # It's not normally a good idea to have two + in a row with 
        # the same test or extractor, but do so to test the behavior.
        patterns = """
nnp : pos[NNP NNPS]
nnps -> &nnp+ &nnp+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'nnps')
        matches = self.matches_tseq('nnps', tseq)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=5, end=7) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=8, end=12) in matches)

        print("test_match_generation done")

    # Like test_match_generation but with reference tokentests.
    def test_tokentest_references(self):
        print("test_tokentest_references")
        patterns = """
nnp : pos[NNP NNPS]
nnp_ref : &nnp
nnps -> &nnp_ref+ &nnp_ref+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'nnps')
        matches = self.matches_tseq('nnps', tseq)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=5, end=7) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=8, end=12) in matches)

        # Check which token test gets recorded, the directly
        # referenced one, or the indirectly referenced one.
        self.assertEqual(matches[matches.index(FAMatch(seq=tseq, begin=5, end=7))].submatches[0].name, "nnp_ref")

        print("test_tokentest_references done")

    def test_tokentest_references_with_substitutions(self):
        print("test_tokentest_references_with_substitutions")
        patterns = """
# Since these two are the same, one has to debug into the code
# to verify that nnp_alt is getting used.
nnp : pos[NNP NNPS]
nnp_alt : pos[NNP NNPS]
nnp_ref : &nnp
nnps ->[nnp=nnp_alt] &nnp_ref+ &nnp_ref+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'nnps')
        matches = self.matches_tseq('nnps', tseq)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=5, end=7) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=8, end=12) in matches)

        # Check which token test gets recorded.
        self.assertEqual(matches[matches.index(FAMatch(seq=tseq, begin=5, end=7))].submatches[0].name, "nnp_ref")

        print("test_tokentest_references_with_substitutions done")

    def test_tokentest_references_with_substitutions_2(self):
        print("test_tokentest_references_with_substitutions_2")
        patterns = """
# Since these two are the same, one has to debug into the code
# to verify that nnp_alt is getting used.
nnp : pos[NNP NNPS]
nnp_alt : pos[NNP NNPS]
nnp_ref : &nnp
nnp_ref_alt : &nnp_alt
nnps ->[nnp_ref=nnp_ref_alt] &nnp_ref+ &nnp_ref+
        """
        self.parse_block(patterns)

        text = "Increased activity occurred in the Rocky Mountain and Western Great Basin Areas."
        tseq = self.tseq_from_text(text, 'nnps')
        matches = self.matches_tseq('nnps', tseq)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=5, end=7) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=8, end=12) in matches)

        # Check which token test gets recorded.
        self.assertEqual(matches[matches.index(FAMatch(seq=tseq, begin=5, end=7))].submatches[0].name, "nnp_ref_alt")

        print("test_tokentest_references_with_substitutions_2 done")

    def test_simple_phrase(self):
        print("test_simple_phrase")
        # * below should probably have been +, but as * it's a good test, 
        # because internally it causes zero-length matches at every token, 
        # which are dropped later in the processing, before getting here.
        patterns = """
lparen       :  { ( }
rparen       :  { ) }
doubleparen -> &lparen &rparen
eitherparen -> ( &lparen | &rparen ) *
maybeparen  -> ( &lparen | &rparen ) ?
        """
        self.parse_block(patterns)

        print("doubleparen")
        self.assertEqual(self.match_count('doubleparen', TEST_TEXT), 4)
        print("eitherparen")
        self.assertEqual(self.match_count('eitherparen', TEST_TEXT), 4)
        print("maybeparen")
        self.assertEqual(self.match_count('maybeparen', TEST_TEXT), 8)

        print("test_simple_phrase done")

    def test_start_end(self):
        print("test_start_end")
        patterns = r"""
num : /^\d+$/
numbers_run -> &num+
all_numbers -> @START @numbers_run @END
        """
        self.parse_block(patterns)

        # These initial cases that don't work entirely correctly are
        # only when scanning for the START and END rules THEMSELVES,
        # as opposed to scanning a different rule that USES them.
        # I'm not aware of any unexpected behavior in the latter case.

        # Expecting 0 for START and END because zero-length matches
        # are generated but later dropped internally (by FA.matches), 
        # though maybe not because the Start/End FAs don't drop them.

        # TODO START seems to give infinite loop.
        # Seemed like doing start = min(start+1, m.end) in FA.scan 
        # might solve that, but it didn't really work as expected.
        # print("START")
        # self.assertEqual(self.match_count('START', "hello there"), 0)

        # END seems to "work" here, but this really isn't much of a test.
        # Because FA.search does "while start < len(toks)", it will stop 
        # trying to match just before END would actually match.
        # print("END")
        # self.assertEqual(self.match_count('END', "hello there"), 0)

        # First pin down the behavior without START/END, so we can show 
        # that using START/END can change the behavior.
        # BTW, this shows it will find the longest contiguous run, not all six 
        # sub-runs.
        print("numbers_run 1")
        start_end_text1 = "1 23 456"
        tseq = self.tseq_from_text(start_end_text1)
        matches = self.matches_tseq('numbers_run', tseq)
        self.assertEqual(len(matches), 1)
        self.assertEqual((matches[0].begin, matches[0].end), (0, 3))
        self.assertEqual(matches[0], FAMatch(seq=tseq, begin=0, end=3))  # equivalent

        # Finds 2 matches here, but 0 matches further below for all_numbers.
        start_end_text2 = "1 bc 456"
        tseq = self.tseq_from_text(start_end_text2)
        matches = self.matches_tseq('numbers_run', tseq)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=2, end=3) in matches)

        # These do seem to work correctly.
        # Ideally we should try to fix all the corner cases in the API,
        # but it's less important that scanning for START/END itself
        # at toplevel should work, than that START/END should work
        # when used as a callout in another rule that is scanned.
        # self.vrm.get_fa("all_numbers").dump()
        print("all_numbers true")
        start_end_text1 = "1 23 456"
        self.assertEqual(self.match_count('all_numbers', start_end_text1), 1)
        print("all_numbers false 1")
        start_end_text2 = "1 bc 456"
        self.assertEqual(self.match_count('all_numbers', start_end_text2), 0)
        print("all_numbers false 2")
        start_end_text3 = "a 23"
        self.assertEqual(self.match_count('all_numbers', start_end_text3), 0)
        print("all_numbers false 3")
        start_end_text4 = "23 def"
        self.assertEqual(self.match_count('all_numbers', start_end_text4), 0)

        # TODO We expect START/END don't work right with coordinators that allow 
        # you to e.g., search for a match within the limits of another match.
        # match(extractor_with_start_end, match(subseqence_extractor, _)).
        # In this situation we want START/END to respect the start/end 
        # of the subsequence, not of the entire sequence.
        # We should first write tests showing that does not work, 
        # then make it work, and change the tests to show that it does.

        print("test_start_end done")

    def test_root(self):
        print("test_root")

        # The built-in ROOT phrase extractor should yield the head word of a sentence
        pattern = "root -> @ROOT"
        self.parse_block(pattern)

        matches = self.matches('root', ROOT_TEXT)
        self.assertEqual(len(matches), 1)
        # Should match the head verb "trigger"
        self.assertEqual((matches[0].begin, matches[0].end), (33, 34))

        print("test_root done")

    def test_phrase_lexicon(self):
        print("test_phrase_lexicon")

        # Assumes tests are being run from project root dir.
        pattern = "greetings Li-> tests/greetings.txt"
        self.parse_block(pattern)

        data = [["Hello!", (0, 1)],
                ["Hi there.", (0, 2)],
                ["How's it going?", (0, 5)]]

        for text, range_ in data:
            matches = self.matches('greetings', text)
            self.assertEqual(len(matches), 1)
            self.assertEqual((matches[0].begin, matches[0].end), range_)

        print("test_phrase_lexicon done")


    # Here I'm not so much interested in the match behavior
    # as in the FA construction and operation.
    # Partly this is connected to how VRManager 
    # checks whether a reference is to a test or not,
    # which used to not recognize imported tests.
    @unittest.skip("debug")
    def test_fa_callouts_vs_non_callouts_1(self):
        print("test_fa_callouts_vs_non_callouts_1")

        patterns = """
a_tt : { a }
a_phr -> &a_tt
p1 -> a
p2 -> &a_tt
p3 -> @a_phr
        """
        self.parse_block(patterns)

        # TODO Try to add a reference above to an imported token test.
        # That would verify that the earlier problem is fixed (though it is).
        for name in ["p1", "p2", "p3"]:
            _, _, expr = self.vrm.lookup_pattern(name)
            print(name, "->", expr)
            ext, _, _ = self.vrm.lookup_extractor(name)  # compiles Regex's to FA's
            # print(name, ext)
            print(ext.dumps())
            print()

        text = "a b c d"
        tseq = self.tseq_from_text(text)

        matches = self.matches_tseq('p1', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)

        matches = self.matches_tseq('p2', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)

        matches = self.matches_tseq('p3', tseq)
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)

        print("test_fa_callouts_vs_non_callouts_1 done")


if __name__ == '__main__':
    print("test_phrase.py starting")
    unittest.main()
    print("test_phrase.py finished")
