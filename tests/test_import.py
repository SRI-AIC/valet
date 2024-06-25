import unittest

from nlpcore.dbfutil import GenericException
from valetrules.match import FAMatch
from valetrules.test.valet_test import ValetTest


class TestImport(ValetTest):

    # Not strictly related to import, but loosely.
    # The problem with the way this is written is that parse_block actually
    # catches and prints exceptions, but otherwise swallows the exceptions.
    @unittest.skip("Not working yet.")
    def test_rule_redefinition_fails(self):
        print("test_rule_redefinition_fails")

        patterns = """
phr1 -> a b
phr1 -> a b
        """
        try:
            self.parse_block(patterns)
        except GenericException:
            pass
        # else:
        #     # self.fail()  # the output of this is unhelpful
        #     raise Exception("Expected GenericException") from None

        patterns = """
phr1 -> a b
phr2 -> c d
        """
        try:
            self.parse_block(patterns)
        except GenericException:
            pass
        # else:
        #     raise Exception("Expected GenericException") from None

        print("test_rule_redefinition_fails done")

    def test_can_redefine_name_in_scope(self):
        print("test_can_redefine_name_in_scope")
        patterns = """
phr1 -> a b
myscope <-
  phr1 -> c d
        """
        self.parse_block(patterns)

        text = "a b c d"
        tseq = self.tseq_from_text(text, "phr1")
        matches = self.matches_tseq('phr1', tseq)
        # print([str(m) for m in matches])
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=2) in matches)

        tseq = self.tseq_from_text(text, "myscope.phr1")
        matches = self.matches_tseq('myscope.phr1', tseq)
        # print([str(m) for m in matches])
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=2, end=4) in matches)

        print("test_can_redefine_name_in_scope done")

    def test_import_builtin_rules_files(self):
        print("test_import_builtin_rules_files")
        patterns = """
syntax <- syntax.vrules
ortho <- ortho.vrules
ner <- ner.vrules
        """
        self.parse_block(patterns)

        text = "Is Paris burning?"

        tseq, matches = self.tseq_and_matches('syntax.verb', text)
        # print([str(m) for m in matches])
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=2, end=3) in matches)

        tseq, matches = self.tseq_and_matches('ortho.cap', text)
        # print([str(m) for m in matches])
        self.assertEqual(len(matches), 2)
        self.assertTrue(FAMatch(seq=tseq, begin=0, end=1) in matches)
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=2) in matches)

        tseq, matches = self.tseq_and_matches('ner.gpe', text)
        # print([str(m) for m in matches])
        self.assertEqual(len(matches), 1)
        self.assertTrue(FAMatch(seq=tseq, begin=1, end=2) in matches)

        print("test_import_builtin_rules_files done")

