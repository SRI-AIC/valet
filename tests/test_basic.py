import pkg_resources
import unittest
# from corpus.LDCCorpus import LDCParagraph
# from nlpcore.dbfutil import SimpleClass
from nlpcore.tseqsrc import TokenSequenceSource

class BasicTestSuite(unittest.TestCase):
    def test_always_true(self):
        assert True

class CsvTestCase(unittest.TestCase):
    def test_csv_tseqsrc(self):
        source_file = pkg_resources.resource_filename(__name__, 'test.csv')
        src = TokenSequenceSource.source_for_type('csv', source_file, column_header="two")
        expected = [['Hello', ',', 'my', 'name', 'is', 'Fred', '.'], ['I', 'am', 'human', '.']]
        for source, tseqs in src.token_sequences():
            # print(source)
            actual = [list(tseq) for tseq in tseqs]
            self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
