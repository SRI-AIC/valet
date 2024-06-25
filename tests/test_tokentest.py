import os
from tempfile import NamedTemporaryFile
import unittest

from valetrules.test.valet_test import ValetTest

from tests.text import TEST_TEXT, TEXTS


def Dont_setUpModule():  # DEBUG, disabled
    import logging.config
    from nlpcore.logging import no_datetime_config
    logging.config.dictConfig(no_datetime_config)


def get_ntf(text):
    with NamedTemporaryFile("wb", delete=False) as f:
        f.write(bytes(text, 'utf-8'))
        f.close()
    return f  # f is closed but still present; use f.name


class TestTokenTest(ValetTest):

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

    # This as an undocumented rule type. (There's also a _c type.)
    def test_membership_lexicon_j(self):
        print("test_membership_lexicon_j")
        # This uses a json format file that allows you to specify multiple
        # rule names and their membership values.
        lexicon = """{
    "a": ["airplane", "apple"],
    "b": ["baby", "boy"]
}"""
        f = get_ntf(lexicon)

        # The rule syntax uses an import style with j{} and the file name.
        patterns = f"""
lex <- j{{{f.name}}}i
        """
        self.parse_block(patterns)
        os.remove(f.name)

        # You have to reference the individual rules with dotted notation.
        self.assertEqual(self.match_count('lex.a', "aardvark airplane apple"), 2)
        self.assertEqual(self.match_count('lex.b', "baby boy bus"), 2)

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

    # This makes use of coordinators, but the intention is to test
    # reference token tests, and in particular their submatch behavior.
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
sel_comma2  ~ select(comma, comma2)
        """
        self.parse_block(patterns)
        text = ". , , ; ; ;"

        # TODO? This gives the expected value 6, but I was somewhat expecting 
        # to see (in the debug printing in match_count) that the matches of 
        # boolpunct contained submatches which are 
        # matches of period, comma, and semicolon, as the phr_* matches do.
        # I guess such tracking has NOT been implemented,
        # and is perhaps not desired.
        self.assertEqual(self.match_count('boolpunct', text), 6)

        # TODO? This is somehat unexpected, to me at least. Expecting 1, 2, 3.
        # This demonstrates what I said above about NOT tracking submatches,
        # so all the TODOs in this method are for basically the same issue.
        self.assertEqual(self.match_count('sel_period', text), 0)
        self.assertEqual(self.match_count('sel_comma', text), 0)
        self.assertEqual(self.match_count('sel_semi', text), 0)

        self.assertEqual(self.match_count('phr_period', text), 1)
        self.assertEqual(self.match_count('phr_comma', text), 2)
        self.assertEqual(self.match_count('phr_semi', text), 3)

        # In contrast to the above, PHRASE matches DO track TT submatches.
        self.assertEqual(self.match_count('sel_period1', text), 1)
        self.assertEqual(self.match_count('sel_comma1', text), 2)
        self.assertEqual(self.match_count('sel_semi1', text), 3)

        self.assertEqual(self.match_count('comma', text), 2)
        self.assertEqual(self.match_count('comma2', text), 2)
        # TODO? Even though this doesn't work when the BOOLEAN EXPRESSION
        # boolpunct is involved, I thought it might work for a SIMPLE REFERENCE.
        # But comma2 matches do NOT contain comma matches as submatches.
        # Token tests currently NEVER record matches of other token tests.
        # (Also, parse matches currently DON'T record matches of token tests, 
        # as these matches would be of edge labels of little interest.)
        self.assertEqual(self.match_count('sel_comma2', text), 0)

    # This mostly has to do with testing internal FA construction.
    # One has to debug into the code to check whether the construction 
    # is as desired or not.
    # Both constructions actually worked, but this test should help
    # switch from the unintended to the intended construction.
    # Here I am primarily interested in phr_comma vs phr_impcomma.
    # But I added other rules and tests for completeness.
    def test_references_to_imports(self):
        print("test_references_to_imports")
        patterns = """
imp <-
    comma     :  { , }
impcomma      :  &imp.comma
phr_comma    -> &imp.comma
phr_impcomma -> &impcomma
sel_comma     ~ select(imp.comma, phr_comma)
sel_impcomma  ~ select(impcomma, phr_impcomma)
        """
        self.parse_block(patterns)
        text = ". , , ; ; ;"

        self.assertEqual(self.match_count('imp.comma', text), 2)
        self.assertEqual(self.match_count('impcomma', text), 2)
        self.assertEqual(self.match_count('phr_comma', text), 2)
        self.assertEqual(self.match_count('phr_impcomma', text), 2)
        self.assertEqual(self.match_count('sel_comma', text), 2)
        self.assertEqual(self.match_count('sel_impcomma', text), 2)

    # Used to have one combined test for pos, lemma, and ner, 
    # but there are now some dependencies between the requirements / 
    # processors in Spacy, so now separate to avoid bleed-over.

    def test_pos_lookup(self):
        print("test_pos_lookup")
        patterns = """
# Had to add NNP here due to bad Spacy POS-ing.
pos      :  pos[NN NNP]
        """
        self.parse_block(patterns)
        text = "The cat sat on the mat."
        self.assertEqual(self.match_count('pos', text), 2)

    def test_lemma_lookup(self):
        print("test_lemma_lookup")
        patterns = """
lemma    :  lemma[sit]
        """
        self.parse_block(patterns)
        text = "The cat sat on the mat."
        tseq = self.tseq_from_text(text, 'lemma')  # debug
        print(tseq.get_token_annotation('lemma', 2))
        self.assertEqual(self.match_count('lemma', text), 1)

    def test_ner_lookup(self):
        print("test_ner_lookup")
        patterns = """
ner      :  ner[O]
        """
        self.parse_block(patterns)
        text = "The cat sat on the mat."
        self.assertEqual(self.match_count('ner', text), 7)

    # nlpcore now lowercases lemma values coming from NLP,
    # hence lemma token tests should always use lowercase.
    def test_lemma_case(self):
        print("test_lemma_case")
        patterns = """
lemma1   :  lemma[sit]
lemma2   :  lemma[SIT]
lemma3   :  lemma[sat]
lemma4   :  lemma[SAT]
        """
        self.parse_block(patterns)
        # I thought NLP might say the lemma is SIT for text2, but it's (now) SAT. 
        # Michael Wessel observed that in Stanza, 
        # "NNP lemma strings seem to preserve case. Others don't."
        # (Sit is a verb, not a proper noun (NNP)).
        text1 = "The cat sat on the mat."
        tseq1 = self.tseq_from_text(text1, 'lemma1')  # debug
        print(tseq1.get_token_annotation('lemma', 2))
        text2 = "THE CAT SAT ON THE MAT."
        tseq2 = self.tseq_from_text(text2, 'lemma2')  # debug
        print(tseq2.get_token_annotation('lemma', 2))
        # Something similar now seems to be the case for Spacy too.
        # Also, with the uppercase SAT, Spacy does not recognize it 
        # as the past tense of sit, and now gives "SAT" as the lemma 
        # (and calls it NNP). 
        # Not sure if that started in 3.5.0, but I suspect so.
        self.assertEqual(self.match_count('lemma1', text1), 1)
        self.assertEqual(self.match_count('lemma2', text1), 0)
        self.assertEqual(self.match_count('lemma3', text2), 1)
        self.assertEqual(self.match_count('lemma4', text2), 0)

if __name__ == '__main__':
    print("test_tokentest.py starting")
    unittest.main()
    print("test_tokentest.py finished")
