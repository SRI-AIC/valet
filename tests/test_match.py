import unittest
from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager
from tests.text import TEST_TEXT, TEXTS
from valetrules.match import FAMatch, FAArcMatch, FARootMatch


class TestMatch(unittest.TestCase):

    def setUp(self):
        self.tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="spacy")
        self.vrm = VRManager()

    def parse_block(self, block):
        self.vrm.forget()
        self.vrm.parse_block(block)

    def matches(self, rulename, text):
        tseq = self.tokenizer.tokens(text)
        # print(tseq.dependency_tree_string())
        matches = self.vrm.scan(rulename, tseq)
        return list(matches)

    def match_count(self, rulename, text):
        return len(self.matches(rulename, text))

    # TODO Later split this up into separate methods.
    def test_match(self):
        print("test_match")

        self.assertLess(FAMatch(begin=0, end=5), FAMatch(begin=1, end=5))
        self.assertLess(FAMatch(begin=0, end=5), FAMatch(begin=1, end=4))
        self.assertLess(FAMatch(begin=0, end=5), FAMatch(begin=1, end=6))
        self.assertEqual(FAMatch(begin=0, end=5), FAMatch(begin=0, end=5))
        self.assertGreater(FAMatch(begin=0, end=5), FAMatch(begin=0, end=4))
        self.assertLess(FAMatch(begin=0, end=5), FAMatch(begin=0, end=6))

        self.assertLess(FAArcMatch(begin=0, end=5), FAArcMatch(begin=1, end=5))
        self.assertLess(FAArcMatch(begin=0, end=5), FAArcMatch(begin=1, end=4))
        self.assertLess(FAArcMatch(begin=0, end=5), FAArcMatch(begin=1, end=6))
        self.assertEqual(FAArcMatch(begin=0, end=5), FAArcMatch(begin=0, end=5))
        self.assertGreater(FAArcMatch(begin=0, end=5), FAArcMatch(begin=0, end=4))
        self.assertLess(FAArcMatch(begin=0, end=5), FAArcMatch(begin=0, end=6))

        print("test_match done")

if __name__ == '__main__':
    print("test_match.py starting")
    unittest.main()
    print("test_match.py finished")
