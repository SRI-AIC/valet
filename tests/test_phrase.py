import unittest
from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager
from tests.text import TEST_TEXT, ROOT_TEXT
from valetrules.match import FAMatch


class TestPhrase(unittest.TestCase):

    def setUp(self):
        self.tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="spacy")
        self.vrm = VRManager()

    def parse_block(self, block):
        self.vrm.forget()
        self.vrm.parse_block(block)

    def matches(self, rulename, text):
        reqs = self.vrm.requirements(rulename)
        self.tokenizer.set_requirements(reqs)
        tseq = self.tokenizer.tokens(text)
        matches = self.vrm.scan(rulename, tseq)
        return list(matches)

    def match_count(self, rulename, text):
        return len(self.matches(rulename, text))

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
        matches = self.matches('nnps', text)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(begin=5, end=7) in matches)
        self.assertTrue(FAMatch(begin=8, end=12) in matches)

        print("test_match_generation done")

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
        matches = self.matches('numbers_run', start_end_text1)
        self.assertEqual(len(matches), 1)
        self.assertEqual((matches[0].begin, matches[0].end), (0, 3))
        self.assertEqual(matches[0], FAMatch(begin=0, end=3))
        # Finds 2 matches here, but 0 matches further below for all_numbers.
        start_end_text2 = "1 bc 456"
        matches = self.matches('numbers_run', start_end_text2)
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(begin=0, end=1) in matches)
        self.assertTrue(FAMatch(begin=2, end=3) in matches)

        # These do seem to work correctly.
        # Ideally we should try to fix all the corner cases in the API,
        # but it's less important that scanning for END itself at toplevel 
        # should work, than that END should work when used as a callout 
        # in another expression.
        # self.vrm.get_fa("all_numbers").dump()
        print("all_numbers true")
        start_end_text1 = "1 23 456"
        self.assertEqual(self.match_count('all_numbers', start_end_text1), 1)
        print("all_numbers false 1")
        start_end_text2 = "1 bc 456"
        self.assertEqual(self.match_count('all_numbers', start_end_text2), 0)

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


if __name__ == '__main__':
    print("test_phrase.py starting")
    unittest.main()
    print("test_phrase.py finished")
