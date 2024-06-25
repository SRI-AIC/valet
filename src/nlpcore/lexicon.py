import csv
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from nlpcore.tokenizer import PlainTextTokenizer, TokenSequence

"""
Provides Lexicon class, providing for efficient storage and matching
of token sequences.
A "prefix tree" implementation is used, using nodes of class LexiconNode.
"""


class LexiconNode(object):
    """Payload being truthy indicates that the node corresponds to
    a complete lexicon entry, as opposed to just a prefix of an entry."""

    def __init__(self):
        self.payload: Any = None
        self.children: Dict[str, 'LexiconNode'] = {}


class Lexicon(object):
    """Defines a set of token sequences via a prefix tree implementation.
    LexiconNodes corresponding to complete (not just prefix) sequences carry
    a truthy 'payload'.
    Uses nlpcore.tokenizer import PlainTextTokenizer to tokenize.
    If case_insensitive is true, lowercases lexicon strings before tokenizing,
    and lowercases incoming token strings when matching.
    """

    def __init__(self, case_insensitive: bool = False):
        self._lexicon = LexiconNode()  # root of tree
        if case_insensitive:
            self._tokr = PlainTextTokenizer()
        else:
            self._tokr = PlainTextTokenizer(preserve_case=True)
        self._source_file: Optional[str] = None
        self.case_insensitive = case_insensitive

    def load_from_strings(self, name: str, strings: Iterable[str]) -> None:
        self._source_file = name
        for line in strings:
            self._process_lexicon_entry(line)

    def load_from_text(self, fname: str) -> None:
        """Uses each line of file as string source to tokenize.
        Payload is the boolean value 'True'."""
        self._source_file = fname
        with open(fname, "r") as fh:
            for line in fh:
                self._process_lexicon_entry(line)

    # I thought about adding **csv_options arg and passing on to csv.reader,
    # but since there is currently no way to specify any of those from VR,
    # I ended up just adding scripts/tsv_to_csv.py to cover my use case.
    # Could add **csv_options to that.
    def load_from_csv(self, fname: str, target_column: int, skip_header=True) -> None:
        """Uses target column as string source to tokenize.
        If skip_header is true, payload consists of a dict mapping header row
        strings to values from the row. If false, there is no header row,
        and zero-based column indices are used as dict keys."""
        self._source_file = fname
        headers = None
        with open(fname, newline='') as fh:
            reader = csv.reader(fh)
            row: List[str]
            for row in reader:
                if headers is None:
                    if skip_header:
                        headers = tuple(row)
                        continue
                    headers = tuple(range(len(row)))  # ints, not strings, FWIW
                entry: str = row[target_column]
                payload = dict(zip(headers, row))
                self._process_lexicon_entry(entry, payload)

    def _process_lexicon_entry(self, entry: str, payload: Any = True) -> None:
        """Tokenizes entry, first lowercasing if case insensitve,
        and enters token sequence into prefix tree."""
        if self.case_insensitive:
            entry = entry.lower()
        tseq: TokenSequence = self._tokr.tokens(entry)
        tlen = len(tseq)

        def enter(index=0, node=self._lexicon):
            if index >= tlen:
                # IIUC, Dayne was saying that he'd probably prefer to probably
                # at least make this an option rather than just leaving it
                # as commented debug code, and probably also not try to check
                # the payloads, as that is kind of application-specific.
                # But I'll just do this to start and we can change later.
                # Plus, if we're case_insensitive that could be the source
                # of duplication, and would you want to force the user to
                # prevent that kind of duplication?
                # if node.payload is not None and payload is not None and \\
                #    payload != node.payload:
                #     print(f"Overwriting payload {node.payload} for entry {entry} with {payload}", file=sys.stderr)
                node.payload = payload
                return
            tok = tseq[index]
            try:
                next_node = node.children[tok]
            except KeyError:
                next_node = node.children[tok] = LexiconNode()
            enter(index+1, next_node)

        enter()

    def matches(self, tseq: TokenSequence, at: int = 0, end=None) -> Iterator[Tuple[int, Any]]:
        """Generator matching tseq starting at 'at' and yielding tuple pairs of
        token index that match ends at (exclusive end), and associated payload."""
        node: LexiconNode = self._lexicon
        if node.payload:
            yield at, node.payload
        if end is None:
            end = len(tseq)
        while at < end:
            tok: str = tseq[at]
            if self.case_insensitive:
                tok = tok.lower()
            try:
                next_node = node.children[tok]
                if next_node.payload:
                    yield at+1, next_node.payload
                node = next_node
            except KeyError:
                break
            at += 1
