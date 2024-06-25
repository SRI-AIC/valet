from typing import List, Tuple
import unittest

from nlpcore.tokenizer import PlainTextTokenizer, TokenSequence
from valetrules.manager import VRManager
from valetrules.match import Match


class ValetTest(unittest.TestCase):
    """Note that the tests are set up to use spacy, not stanza."""

    def setUp(self):
        self.tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="spacy")
        self.vrm = VRManager()

    def parse_block(self, block: str) -> None:
        self.vrm.forget()
        self.vrm.parse_block(block)

    def tseq_from_text(self, text: str, patname=None) -> TokenSequence:
        if patname is not None:
            reqs = self.vrm.requirements(patname)
            self.tokenizer.set_requirements(reqs)
        tseq = self.tokenizer.tokens(text)
        return tseq

    def matches_tseq(self, patname: str, tseq: TokenSequence) -> List[Match]:
        matches = self.vrm.scan(patname, tseq)
        matches = list(matches)
        # Have to do these after the scan (and list).
        # print(tseq.dependency_tree_string())
        # print(patname, [str(m) for m in matches])
        return matches

    def matches(self, patname: str, text: str) -> List[Match]:
        # print(f"In matches with {patname}, {text}")
        tseq = self.tseq_from_text(text, patname)
        return self.matches_tseq(patname, tseq)

    # We often need the tseq in order to construct expected matches
    # to assert against.
    def tseq_and_matches(self, patname: str, text: str) -> Tuple[TokenSequence, List[Match]]:
        tseq = self.tseq_from_text(text, patname)
        matches = self.matches_tseq(patname, tseq)
        return tseq, matches

    def match_count(self, patname: str, text: str) -> int:
        return len(self.matches(patname, text))
