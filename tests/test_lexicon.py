from unittest import TestCase

from nlpcore.lexicon import Lexicon
from nlpcore.tokenizer import PlainTextTokenizer

class LexiconTest(TestCase):

    def test_it_works(self):
        lexicon = Lexicon(case_insensitive=False)
        data = [
            "Now is",
            "Now is the time",
            "Now is not the time",
        ]
        lexicon.load_from_strings("dummy", data)

        tokr = PlainTextTokenizer(preserve_case=True)
        for datum in data:
            tseq = tokr.tokens(datum)
            # Which of the lexicon tseqs can be found within this tseq
            # (also from the lexicon)?
            # Each should be found within itself, and the first one should
            # be found within each.
            matches = list(lexicon.matches(tseq))
            # print(matches)
            # [(2, True)]
            # [(2, True), (4, True)]
            # [(2, True), (5, True)]
            self.assertGreaterEqual(len(matches), 1)
            self.assertEqual(matches[-1][0], len(tseq))

    # def test_my_file(self):
    #     lex = Lexicon()
    #     lex.load_from_csv("/Users/sasseen/Downloads/CID-Synonym-SMILES.tsv", 1, False, dialect="")
