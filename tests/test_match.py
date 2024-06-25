import unittest

from valetrules.match import FAMatch, FAArcMatch
from valetrules.test.valet_test import ValetTest

from tests.text import TEST_TEXT


class TestMatch(ValetTest):

    # TODO Later split this up into separate methods.
    def test_match(self):
        print("test_match")

        tseq = self.tseq_from_text(TEST_TEXT)

        self.assertLess(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=1, end=5))
        self.assertLess(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=1, end=4))
        self.assertLess(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=1, end=6))
        self.assertEqual(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=0, end=5))
        self.assertGreater(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=0, end=4))
        self.assertLess(FAMatch(seq=tseq, begin=0, end=5), FAMatch(seq=tseq, begin=0, end=6))

        self.assertLess(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=1, end=5))
        self.assertLess(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=1, end=4))
        self.assertLess(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=1, end=6))
        self.assertEqual(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=0, end=5))
        self.assertGreater(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=0, end=4))
        self.assertLess(FAArcMatch(seq=tseq, begin=0, end=5), FAArcMatch(seq=tseq, begin=0, end=6))

        # There are probably more cases that could be added here.
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=5).overlaps(FAMatch(seq=tseq, begin=1, end=5)))
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=6).overlaps(FAMatch(seq=tseq, begin=1, end=5)))
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=5).overlaps(FAMatch(seq=tseq, begin=1, end=6)))
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=5).overlaps(FAMatch(seq=tseq, begin=1, end=5)))
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=5).overlaps(FAMatch(seq=tseq, begin=0, end=5)))
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=5).overlaps(FAMatch(seq=tseq, begin=0, end=6)))
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=6).overlaps(FAMatch(seq=tseq, begin=1, end=5)))

        print("test_match done")


if __name__ == '__main__':
    print("test_match.py starting")
    unittest.main()
    print("test_match.py finished")
