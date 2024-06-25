import logging
from typing import Iterator, List, Optional, Tuple

from nlpcore.dbfutil import GenericException
from nlpcore.tseqsrc import TokenSequenceSource, TokenSequence
from ..manager import VRManager
from ..match import Match, Frame


_logger = logging.getLogger(f"{__name__}.<module>")


class Spooler:
    """
    Handles looping operations over documents and tseqs from a
    TokenSequenceSource, including calling VRManager pattern
    scanning methods on each tseq looped over.
    """

    # It appears this is stored at class level so that multiple instances
    # share the value among them, and/or preserve it across re-instantiation
    # of a Spooler.
    # There are several different places in the GUI code that create
    # and hold spooler instances.
    # Besides the main one in textpane.py, there are others in context.py,
    # cull.py, and extract.py.
    # I'm not sure whether those other files are currently used.
    SOURCE: Optional[TokenSequenceSource] = None

    @classmethod
    def set_source(cls, source: TokenSequenceSource) -> None:
        if cls.SOURCE is not None and cls.SOURCE != source:
            raise ValueError("Conflicting source indicated")
        cls.SOURCE = source

    @classmethod
    def get_source(cls) -> Optional[TokenSequenceSource]:
        return cls.SOURCE

    def __init__(self, vrm: VRManager, filename_cb=lambda fname: None):
        if self.SOURCE is None:
            raise GenericException(msg="Set Spooler.SOURCE before instantiating a Spooler")
        self.feed = self.SOURCE.token_sequences()
        self.vrm = vrm
        self.filename_cb = filename_cb
        self.label: Optional[str] = None  # scrolling start point (docname)
        self.tseqs: List[TokenSequence] = []
        self.stop = False

    def set_requirements(self, reqs) -> None:
        self.SOURCE.set_requirements(reqs)

    def current_text(self) -> Optional[str]:
        if len(self.tseqs) == 0:
            return None
        # Assuming all tseqs share the same text.
        return self.tseqs[0].text

    def current(self) -> Tuple:
        """Return current docname, tseqs, and text."""
        return self.label, self.tseqs, self.current_text()

    def current_token_sequences(self) -> List[TokenSequence]:
        return self.tseqs

    # Note FWIW this is not called from TextPane.next().
    # Instead, a new Spooler.scroll() generator is created there and
    # iterated just once (__next__ called just once).
    # Rather, this method is called from Spooler.scroll().
    def next(self) -> Optional[Tuple[str, List[TokenSequence]]]:
        """
        Return (and store) the next pair of doc label and tseqs from the feed.
        If at end of feed, return None, and rewind the feed.
        """
        _logger.debug("In Spooler.next with fname %s", self.label)
        while True:
            next_item = next(self.feed, None)
            if next_item is None:
                self.rewind()
                self.label, self.tseqs = None, []
                return None
            if len(next_item[1]) > 0:
                self.label, self.tseqs = next_item
                break
            else:
                # Keep looking for len > 0.
                _logger.info("Doc %s contains no tseqs", self.label)
        return self.label, self.tseqs

    # Note FWIW that only when called from Spooler.scan() is this used to
    # generate multiple values. In other places, the generator is created
    # but dropped after generating only the first value.
    def scroll(self) -> Iterator[Tuple[str, List[TokenSequence]]]:
        """
        Yield every item in the corpus (doc label, list of token sequences),
        starting after the feed's current position. Wraps around (rewinds)
        once if needed, stopping at the original position.
        Each iteration first advances to the next "document".
        """
        _logger.debug("In Spooler.scroll starting from fname %s", self.label)
        start_label = self.label
        while True:
            next_item = self.next()
            if next_item is None:
                if start_label is None:
                    # This indicates there are no docs.
                    _logger.debug("Spooler.scroll() finds no documents")
                    self.filename_cb("No documents")
                    return
                else:
                    _logger.debug("Spooler.scroll() NOT rewinding, but clearing fname in GUI")
                    self.filename_cb("")
                    # self.filename_cb("(cleared, not yet repopulated)")  # DEBUG
                    # Go back to top of while loop and get first item.
            else:
                label, _ = next_item
                _logger.debug("Spooler.scroll() updating fname in GUI to %s", label)
                self.filename_cb(label)
                yield next_item
                if label == start_label:
                    return

    # Note FWIW that when called from TextPane.scan, the generator created is
    # dropped after yielding only one value (or zero if no matches or stopped).
    def scan(self, name, yield_non_matching=False, progress_cb=None) -> Iterator[Tuple[str, List[TokenSequence], List[Tuple[Match, int, int]]]]:
        """
        Yield tuples of (doc label, tseqs, matches info) for each item in the
        corpus that has matches (or all items if yield_non_matching is true),
        starting at the feed's current position. Wraps around (rewinds)
        once if needed, stopping at the original position.
        """
        self.stop = False
        count = 0
        for item in self.scroll():
            if item is None or self.stop:
                return
            count += 1
            self.label, self.tseqs = item
            if progress_cb is not None:
                progress_cb(self.label, count)
            matches = list(self.pattern_matches(name))  # matches plus absolute offsets
            if len(matches) > 0 or yield_non_matching:
                yield self.label, self.tseqs, matches

    def stop_command(self) -> None:
        self.stop = True

    def rewind(self) -> None:
        """
        Reset feed to beginning of document sequence.
        """
        _logger.debug("In Spooler.rewind")
        # Get a new iterator, as the prev one either was consumed,
        # or we want to restart at the beginning.
        self.feed = self.SOURCE.token_sequences()
        # TODO? Should this reset any state, like self.label?
        # I'm wondering about the call from TextPane.rewind.
        # self.label = None

    def pattern_matches(self, name) -> Iterator[Tuple[Match, int, int]]:
        """
        Yield all matches of the given pattern in all the current tseqs,
        as (match, start_offset, end_offset).
        """
        # _logger.debug("Spooler.pattern_matches clearing recorded tseqs matching patterns, scanning for matches")
        self.vrm.clear_recorded()
        for tseq in self.tseqs:
            # _logger.debug("Spooler.pattern_matches running pattern '%s' on tseq '%s'" % (name, tseq.tokens))
            for m in self.vrm.scan(name, tseq):
                # TODO Maybe let the caller do this if it wants to, and just
                # return the matches here? That would simplify the code.
                # For example, Culler does not use these offsets.
                # Also, frames() below does not adjust the offsets.
                soffs = m.start_offset(absolute=True)
                eoffs = m.end_offset(absolute=True)
                # Like printing the dependency parse tree, I find this
                # nearly indispensable. We/I had this in vrgui previously.
                print(m)
                yield m, soffs, eoffs

    def frames(self, name) -> Iterator[Frame]:
        """
        Yield all frames (if any, via match.get_frame()) from all matches
        of the given pattern in all the current tseqs.
        """
        # _logger.debug("Spooler.frames clearing recorded tseqs matching patterns, scanning for matches")
        self.vrm.clear_recorded()
        for tseq in self.tseqs:
            # _logger.debug("Spooler.frames running pattern '%s' on tseq '%s'" % (name, tseq.tokens))
            for match in self.vrm.scan(name, tseq):
                frame = match.get_frame()
                if frame is not None:
                    yield frame
