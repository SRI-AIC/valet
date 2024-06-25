import logging
from tkinter import WORD
import traceback
from typing import Iterator, List, Optional, Tuple

from nlpcore.tseqsrc import TokenSequenceSource, TokenSequence
from ..manager import VRManager
from ..match import Match, Frame
from .pane import Pane
from .spooler import Spooler


_logger = logging.getLogger(f"{__name__}.<module>")


# Note that the Application frame has a TextPane, but that is not the only
# TextPane; Culler has one too.
class TextPane(Pane):
    """
    Supports display of document text in pane, cycling through documents,
    running patterns against documents, and mouse-driven user operations
    within pane.
    """
    label: Optional[str]  # docname of doc in pane

    def __init__(self, parent, data_source: TokenSequenceSource, vrmanager: VRManager):
        # The spooler handles cycling through documents and
        # running patterns against documents.
        self.data_source = data_source
        Spooler.set_source(data_source)
        self.spooler = Spooler(vrmanager, lambda filename: parent.filename(filename))

        super().__init__(parent, text_height=8, font_size=20, font='Times', wrap=WORD)

        text_widget = self.text_widget
        text_widget.bind('<<Selection>>', self.respond_selection)
        text_widget.bind('<ButtonRelease-1>', self.respond_button_release)
        text_widget.bind('<Shift-Button>', self.expand_text_pane_term)
        text_widget.configure(state='disabled')
        # text_widget.bind('<Control-Button>', self.present_learning_example)

        self.selection_changed = False

    def set_requirements(self, reqs) -> None:
        self.spooler.set_requirements(reqs)

    def set_spooler(self, spooler) -> None:
        self.spooler = spooler

    # def get_label(self) -> Optional[str]:
    #     """Source (document) name."""
    #     return self.label

    def clear(self) -> None:
        self.clear_tags()

    def clear_tags(self) -> None:
        """Remove all tags in the text window, eg for match highlighting."""
        self.text_widget.tag_delete(*self.text_widget.tag_names())

    def populate(self) -> None:
        """Put the spooler's current document text into the pane,
        and instantiate a new TextManager for it."""
        _logger.debug("In TextPane.populate")
        label, tseqs, text = self.spooler.current()
        # _logger.debug("TextPane.populate setting self.label to '%s'", label)
        # Not currently used. Was considering that if this is None
        # (ie "No documents") then don't print "No matches" elsewhere.
        self.label = label
        if text is not None:
            self.insert(text)

    # Within this file we call directly to self.spooler.scroll(),
    # but we define this method for outside callers to use.
    def scroll(self) -> Iterator[Tuple[str, List[TokenSequence]]]:
        """
        Yield every item in the corpus (doc label, list of token sequences),
        starting after the current position. Wraps around (rewinds)
        once if needed, stopping at the original position.
        Each iteration first advances to the next "document".
        """
        for item in self.spooler.scroll():
            yield item

    def next(self, pname) -> None:
        """Advance to the next file (document) and display any matches.
        Wraps around to start of corpus when end reached."""
        _logger.debug("In TextPane.next")
        for _ in self.spooler.scroll():
            matches = []
            if pname is not None:
                matches = list(self.spooler.pattern_matches(pname))  # matches plus absolute offsets
            # TODO Why do we display matches here and in rewind, but with scan
            # the caller is responsible?
            # I tend to think our scan should do the displaying too.
            self.display_matches(matches, refresh=True)
            break

    def scan(self, name) -> Tuple[str, List[Tuple[Match, int, int]]]:
        """Find the next document with matches, return the text and matches.
        Wraps around to start of corpus when end reached."""
        _logger.debug("In TextPane.scan")
        def report_progress(label, count):
            self.parent.message("Scanning block %d (%s)" % (count, label))
        matches = []
        for item in self.spooler.scan(name, progress_cb=report_progress):
            _, _, matches = item
            break
        return self.get_text(), matches

    def stop_command(self) -> None:
        """Stop a scan operation in progress."""
        self.spooler.stop_command()

    def rewind(self, pname) -> None:
        """Go back to the first file (document) and display any matches."""
        _logger.debug("In TextPane.rewind")
        self.spooler.rewind()
        for _ in self.spooler.scroll():
            break
        self.populate()
        if pname is not None:
            self.display_pattern_matches(pname)

    def display_pattern_matches(self, pattern_name):
        """Run pattern, and show matches in the pane."""
        try:
            matches = list(self.spooler.pattern_matches(pattern_name))  # matches plus absolute offsets
        except Exception as ex:
            # matches = []
            # TODO? replace with a broken region, or otherwise indicate problem in GUI?
            # See PatternPane.get_pattern_regions(), which does that.
            # Does that happen here somehow already?
            traceback.print_exc()
            print("VRGUI PATTERN RUN ERROR: When running pattern '%s': %s" % (pattern_name, ex))
            raise
        self.display_matches(matches, refresh=False)

    def display_matches(self, matches: List[Tuple[Match, int, int]], refresh=True):
        """
        Display the given matches (dropping old ones) in the current text, and the count.
        If refresh=True, first put the current text into the text widget.
        """
        if refresh:
            self.populate()
        else:
            # Delete old match tags (and all other tags -- why?)
            self.clear_tags()
        for m, soffs, eoffs in matches:
            si = self.offset_to_index(soffs)
            ei = self.offset_to_index(eoffs)
            self.text_widget.tag_add('match', si, ei)
        self.text_widget.tag_config('match', background="light blue")
        if len(matches) == 0:
            self.parent.message("No matches")
        else:
            self.parent.message("%d matches" % len(matches))
            self.text_widget.see(si)

    def frames(self, name) -> Iterator[Frame]:
        """
        Yield all frames (if any, via match.get_frame()) from all matches
        of the given pattern in all the current tseqs.
        """
        for frame in self.spooler.frames(name):
            yield frame

    def respond_selection(self, *args) -> None:
        self.selection_changed = True

    def respond_button_release(self, *args) -> None:
        """
        Respond to mouse actions in text widget.
        If selection made, show dependency path between start and end tokens.
        If not, show POS info for token to right of current cursor.
        ...
        """
        self.parent.message("")  # clear old msg
        if self.selection_changed:
            selected = self.get_selected_tokens()
            if selected:
                self.show_dependency_path(*selected)
        selected = self.get_selected_token()
        if selected:
            self.show_word_info(*selected)
        # selected = self.get_selected_token(matches_only=True)
        # if selected:
        #     tseq, toki = selected
        #     tok = tseq[toki]
        #     self.culled[tok] = True
        #     pattern = "cull: { %s }" % ' '.join(c for c in self.culled.keys() if self.culled[c])
        #     self.parent.write_to_clipboard(pattern)

    def expand_text_pane_term(self) -> None:
        # TODO?
        pass

    def get_indicated_tokens(self, matches_only: bool):
        tw = self.text_widget
        selection = tw.tag_nextrange('sel', '1.0')
        if selection == '' or selection == ():
            if matches_only:
                if 'match' not in tw.tag_names('current'):
                    return None, None, None
            tseqi, tokeni = self.get_token_indexes('current')
            if tseqi is None:
                return None, None, None
            else:
                return tseqi, tokeni, tokeni
        else:
            starti, endi = selection
            if matches_only:
                matches = tw.tag_ranges('match')
                matches = [(matches[2*i], matches[2*i+1]) for i in range(len(matches) // 2)]
                # TODO: Compiler says p not used; looks like we're not calling the lambda?
                if not any(lambda p: tw.compare(p[0], '<=', starti) and tw.compare(p[1], '>=', endi) for p in matches):
                    return None, None, None
            start_tseq, start_token = self.get_token_indexes(starti, True)
            end_tseq, end_token = self.get_token_indexes(endi, False)
            if start_tseq is None or end_tseq is None or start_tseq != end_tseq:
                return None, None, None
            else:
                return start_tseq, start_token, end_token

    def get_selected_tokens(self, matches_only: bool = False):
        """
        Returns tseq, start_token, end_token only if different tokens in the same sequence are selected.
        """
        tseq, start_token, end_token = self.get_indicated_tokens(matches_only)
        if tseq is None or start_token >= end_token:
            return None
        tseqs = self.spooler.current_token_sequences()
        return tseqs[tseq], start_token, end_token

    def get_selected_token(self, matches_only: bool = False):
        """
        Returns selected tseq and token index if a single token is selected.
        """
        tseq, start_token, end_token = self.get_indicated_tokens(matches_only)
        if tseq is None or start_token != end_token:
            return None
        tseqs = self.spooler.current_token_sequences()
        return tseqs[tseq], start_token

    def show_dependency_path(self, tseq, start_token, end_token) -> None:
        """
        Show in message widget the dependency path (if any) associated with
        the selection (if any), if dependency path calculation is enabled.
        Return True if there is a selection, otherwise False.
        """
        if hasattr(tseq, 'find_paths'):
            for path in tseq.find_paths(start_token, end_token):
                self.parent.message("Path between '%s' and '%s': %s" % (tseq[start_token], tseq[end_token], " ".join(path)))
                # self.parent.entities_and_paths.append("%s and %s\t%s" % (tseq[start_token], tseq[end_token], path))
                # self.parent.string_var_patterns.set(self.parent.entities_and_paths)
                break
            if hasattr(tseq, 'dependency_tree_string'):
                s = tseq.dependency_tree_string()
                print(s)
        else:
            self.parent.message("Dependency paths not supported")

    def show_word_info(self, tseq, tokeni) -> None:
        """
        Show the POS and other (tag, lemma, NER) info for the token with the
        current cursor (or the token to its right if cursor is not in a token).
        """
        # As noted elsewhere, we interchange the terms "pos" and "tag"
        # relative to Spacy's usage.
        pos = tseq.get_token_annotation('pos', tokeni)
        tag = tseq.get_token_annotation('tag', tokeni)
        lemma = tseq.get_token_annotation('lemma', tokeni)
        ner = tseq.get_token_annotation('ner', tokeni)
        self.parent.message("Fine POS of '%s' is %s, coarse POS (aka tag[]) is %s, lemma is %s, ner is %s" % (tseq[tokeni], pos, tag, lemma, ner))

    # This is called
    # - with start=True and an index from the start of a selection,
    # - with start=False and an index from the end of a selection, and
    # - with start defaulting to True and index = 'current'.
    def get_token_indexes(self, text_index, start: bool = True) -> Tuple[Optional[int], Optional[int]]:
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
        offset = self.index_to_offset(text_index)  # char offset from start of text
        tseqs = self.spooler.current_token_sequences()
        for tseqi, tseq in enumerate(tseqs):
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
                            return tseqi - 1, len(tseqs[tseqi - 1]) - 1
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
            tsslen = len(tseqs)
            if tsslen > 0:
                return tsslen - 1, len(tseqs[tsslen - 1]) - 1
            else:
                # No tokens at all.
                return None, None
