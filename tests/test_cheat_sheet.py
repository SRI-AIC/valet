import io
import os
from pathlib import Path
import unittest
from ordered_set import OrderedSet

from nlpcore.sentencer import Sentencer
from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager


class TestCheatSheet(unittest.TestCase):

    def setUp(self):
        self.current_path = Path(os.path.dirname(os.path.realpath(__file__)))

    def get_tseq_and_normed(self, input_file):
        # Load the tokenizer
        tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="spacy")
        sentencer = Sentencer(blank_line_terminals=True)

        # Read in the text file
        f = io.open(self.current_path / input_file, mode="r", encoding="utf-8")
        text = f.read()
        f.close()

        # Segment the file into sentences
        result = list()
        for s in sentencer.sentences(text):
            # Apply the tokenizer to each sentence, then get normalized version
            tseq = tokenizer.tokens(s.sentence_text())
            normed = tseq.get_normalized_text()
            result.append((tseq, normed))
        return result

    def test_cheat_sheet(self):
        print("test_cheat_sheet")

        vrm = VRManager()
        vrm.forget()
        vrm.parse_file(self.current_path / 'cheat_sheet.vrules')

        # make sure all the expressions were parsed
        builtins = set(vrm.builtins())
        self.assertEqual(len(builtins), 1+3)  # 1 token test, 3 phrase (fa)
        self.assertEqual(len(list(vrm.fa_expressions)), 1+3)  # 3 built-in
        self.assertEqual(len(list(vrm.fa_lexicon_imports)), 0)
        self.assertEqual(len(list(vrm.test_expressions)), 26+1)  # 1 built-in
        self.assertEqual(len(list(vrm.import_expressions)), 2)
        self.assertEqual(len(list(vrm.coord_expressions)), 0)
        self.assertEqual(len(list(vrm.dep_fa_expressions)), 0)
        self.assertEqual(len(list(vrm.frame_expressions)), 0)

        # Ready the test texts for scanning
        wiki_tokens = self.get_tseq_and_normed("wiki_test_text.txt")
        ascii_tokens = self.get_tseq_and_normed("ascii_test_text.txt")

        # Scan for expression matches
        # This is designed to be eyballed, so enable printing.
        # But sometimes we don't want all that output, so enable disabling.
        do_print = False
        patterns = OrderedSet(list(vrm.test_expressions) + list(vrm.fa_expressions)) - builtins
        for pattern in patterns:  # pattern names
            if do_print: print(pattern)
            match_set = set()
            for (tseq, normed) in wiki_tokens:
                for match in vrm.scan(pattern, tseq):
                    match_set.add(normed[match.start_offset():match.end_offset()])
            for (tseq, normed) in ascii_tokens:
                for match in vrm.scan(pattern, tseq):
                    match_set.add(normed[match.start_offset():match.end_offset()])
            if do_print: print(match_set)

        print("test_cheat_sheet done")

if __name__ == '__main__':
    print("test_cheat_sheet.py starting")
    unittest.main()
    print("test_cheat_sheet.py finished")
