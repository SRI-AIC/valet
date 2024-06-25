import re
from typing import List
from nlpcore.tokenizer import TokenSequence
from .pane import Pane


# This seems entirely obsolete.
# Recently TextPane was instantiatiang one, but used it only to store the label.
# Got rid of that. Note TextPane has its own get_token_indexes method.
class TextManager:
    """
    Provides functionality for converting tkinter text indices (L.C, etc) 
    to tuple with valet/nlpcore token sequence index and token index.
    """

    def __init__(self, label: str, tseqs: List[TokenSequence], pane: Pane) -> None:
        self.label = label
        self.tseqs = tseqs
        self.pane = pane
        self.text = tseqs[0].text if tseqs is not None and len(self.tseqs) > 0 else None
        # self.line_offsets = [0]
        # for m in re.finditer('\n', self.text):
        #     self.line_offsets.append(m.end())

    def get_label(self):
        return self.label

    def get_text(self) -> str:
        return self.text

    # Not called?
    # def populate(self):
    #     self.pane.insert(self.text)

    # This is called
    # - with start=True and an index from the start of a selection,
    # - with start=False and an index from the end of a selection, and
    # - with start defaulting to True and index = 'current'.
    def get_token_indexes(self, text_index, start=True):
        """
        If a token contains the given (L.C or similar) text_index,
        return the token sequence index (tseqi) and the token index
        relative to that token sequence (toki) of that token.

        If the text_index is outside any token or at the edge of a token,
        then when start=True (default), return the token (if any) to the right
        of the index, and when start=False, return the token (if any) to the
        left of the index.
        If there is no such token, return a pair of None values.

        Note that when start=False (i.e., we're looking for the end index
        of a selection), the returned tseqi/toki pair is inclusive (']'),
        not exclusive (')'), unlike selection L.C indices or char offsets.
        """
        # The code below assumes there can be zero token_sequences
        # (empty document), but not empty tseqs (empty sentences).
        # (In fact, next_text_block will probably disallow empty document,
        # but no harm in allowing for it here.)
        offset = self.pane.index_to_offset(text_index)  # char offset from start of text
        for tseqi, tseq in enumerate(self.tseqs):
            for toki in range(len(tseq)):
                soffs = tseq.offset + tseq.get_normalized_offset(toki)  # char offset of start of this token
                if start:
                    if soffs + tseq.lengths[toki] > offset:
                        # This token is the first to end strictly after
                        # the given offset so it's the one we want.
                        return tseqi, toki
                else:
                    if soffs >= offset:
                        # This token is the first to start at or after
                        # the given offset, so we want the previous token
                        # (the last one to start before the given offset).
                        if toki > 0:
                            return tseqi, toki - 1
                        elif tseqi > 0:
                            return tseqi - 1, len(self.tseqs[tseqi - 1]) - 1
                        else:
                            # There's no previous token; first token of
                            # first sequence starts at or after offset.
                            return None, None
        if start:
            # No tokens ended strictly after the given offset,
            # so all tokens (if there are any) ended at or before that offset.
            return None, None
        else:
            # No tokens started at or after the given offset,
            # so all (if there are any) started before that offset,
            # and we want the last one.
            tsslen = len(self.tseqs)
            if tsslen > 0:
                return tsslen - 1, len(self.tseqs[tsslen - 1]) - 1
            else:
                # No tokens at all.
                return None, None
