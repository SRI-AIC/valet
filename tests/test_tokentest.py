import unittest
from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager
from tests.text import TEST_TEXT, TEXTS

class TestTokenTest(unittest.TestCase):

    def setUp(self):
        self.tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="spacy")
        self.vrm = VRManager()

    def parse_block(self, block):
        self.vrm.forget()
        self.vrm.parse_block(block)

    def matches(self, rulename, text):
        tseq = self.tokenizer.tokens(text)
        # print("tokens:", list(enumerate(tseq)))
        matches = self.vrm.scan(rulename, tseq)
        # Have to do this after the scan.
        # print(tseq.dependency_tree_string())
        matches = list(matches)
        # print(rulename, [str(m) for m in matches])
        return matches

    def match_count(self, rulename, text):
        return len(self.matches(rulename, text))

    def test_membership(self):
        print("test_membership")
        patterns = """
period      :  { . }
comma       :  { , }
semicolon   :  { ; }
        """
        self.parse_block(patterns)
        self.assertEqual(self.match_count('period', TEST_TEXT), 2)
        self.assertEqual(self.match_count('comma', TEST_TEXT), 0)
        self.assertEqual(self.match_count('semicolon', TEST_TEXT), 2)

    def test_boolean(self):
        print("test_boolean")
        patterns = """
period      :  { . }
comma       :  { , }
semicolon   :  { ; }
boolpunct   : &period or &comma or &semicolon
        """
        self.parse_block(patterns)
        # This should be true of any input text
        for text in TEXTS:
            self.assertEqual(self.match_count('boolpunct', text),
                             self.match_count('period', text)
                             + self.match_count('comma', text)
                             + self.match_count('semicolon', text))

    def test_boolean_2(self):
        print("test_boolean_2")
        patterns = """
period      :  { . }
notperiod   : not &period
        """
        self.parse_block(patterns)
        text1 = ". . , , ; ;"
        self.assertEqual(self.match_count('notperiod', text1), 4)

    # This makes use of coordinators, but the intention is to test booleans.
    def test_references(self):
        print("test_references")
        patterns = """
period      :  { . }
comma       :  { , }
comma2     :  &comma
semicolon   :  { ; }
boolpunct   : &period or &comma or &semicolon
sel_period ~ select(period, boolpunct)
sel_comma  ~ select(comma, boolpunct)
sel_semi   ~ select(semicolon, boolpunct)
phr_period -> &period
phr_comma -> &comma
phr_semi -> &semicolon
sel_period1 ~ select(period, phr_period)
sel_comma1  ~ select(comma, phr_comma)
sel_semi1   ~ select(semicolon, phr_semi)
sel_comma2 ~ select(comma, comma2)
        """
        self.parse_block(patterns)
        text = ". , , ; ; ;"

        # TODO? This gives the expected value 6, but I was somewhat expecting 
        # to see (in the debug printing in match_count) that the matches of 
        # boolpunct contained submatches which are 
        # matches of period, comma, and semicolon, as the phr_* matches do.. 
        # I guess such tracking hasn't been implemented. 
        self.assertEqual(self.match_count('boolpunct', text), 6)

        # TODO? This is somehat unexpected, to me at least. Expecting 1, 2, 3.
        # This demonstrates what I said above about not tracking submatches, 
        # so all the TODOs in this method are for basically the same issue.
        self.assertEqual(self.match_count('sel_period', text), 0)
        self.assertEqual(self.match_count('sel_comma', text), 0)
        self.assertEqual(self.match_count('sel_semi', text), 0)

        self.assertEqual(self.match_count('phr_period', text), 1)
        self.assertEqual(self.match_count('phr_comma', text), 2)
        self.assertEqual(self.match_count('phr_semi', text), 3)

        # In contrast to the above, phrase matches do track TT submatches.
        self.assertEqual(self.match_count('sel_period1', text), 1)
        self.assertEqual(self.match_count('sel_comma1', text), 2)
        self.assertEqual(self.match_count('sel_semi1', text), 3)

        self.assertEqual(self.match_count('comma', text), 2)
        self.assertEqual(self.match_count('comma2', text), 2)
        # TODO? Even thought this doesn't work when the boolean expression 
        # boolpunct is involved, I thought it might work for a simple reference.
        # But comma2 matches don't contain comma matches as submatches.
        self.assertEqual(self.match_count('sel_comma2', text), 0)

if __name__ == '__main__':
    print("test_tokentest.py starting")
    unittest.main()
    print("test_tokentest.py finished")
