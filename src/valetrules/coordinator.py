from abc import abstractmethod
from itertools import chain
import logging
from typing import Iterable, Optional, TYPE_CHECKING

from ordered_set import OrderedSet

from nlpcore.dbfutil import GenericException, SimpleClass
from nlpcore.tokenizer import TokenSequence
from .extractor import Extractor
from .match import FAMatch, CoordMatch, DelegatedCoordMatch
if TYPE_CHECKING:
    from .manager import VRManager

"""
Provides the Coordinator base class and numerous subclasses largely
mirroring the taxonomy of coordinator expressions -- MatchCoordinator,
SelectCoordinator, FilterCoordinator, OverlapsCoordinator, etc.
Coordinator expressions are parsed by the coordinatorexp module into
a tree of Coordinator instances mirroring the structure of the expression.
"""


_logger = logging.getLogger(f"{__name__}.<module>")


# TODO? Nearly all the coordinators still directly reference match.begin/end,
# rather than calling match.get_extent().
# There's a good chance that implies bugs if the match class is unknown
# (so multiple possible conventions) or if there are reversed indices.
# However, some references to .begin/end are OK or even mandatory;
# the trick is recognizing where they're not.

# TODO? Note that in practice none of the coordinators are assigned
# name attributes (except for None in Coordinator.__init__),
# so the coordinators passing self.name to all the match objects
# they create does not have any real effect.
# (I.e., just as well to set to None in match __init__ methods.)
#
# [I did see at least one exception to the above, so need further
# investigation.]
#
# Most match objects have their name assigned in VRManager._scan (or _matches),
# and ones that don't are ones associated with internal subexpressions
# of named expressions, which don't get to that _scan method to get named.

class Coordinator(Extractor, SimpleClass):
    """Base class for other coordinators."""

    # Label seems pretty obsolete; see where passed in coordinatorexp.py.
    def __init__(self, manager: Optional['VRManager'], label: Optional[str] = None, **kwargs):
        super().__init__(manager, **kwargs)
        self.label = label

    def matches(self, seq, start=0, end=None, substitutions=None):
        """This matches implementation utilizes scan but only yields matches
        anchored at the indicated start position, so is no more efficient than scan."""
        for m in self.scan(seq, start=start, end=end, substitutions=substitutions):
            if m.begin == start:
                yield m
            # Scanning doesn't always return matches ordered by begin value.
            # If it did, we could do "else: return" here.


# "Base" here indicates base stream, not base class.
# The coordinators take match streams as input and produce match streams
# as output, so we need to have a way of producing an initial match stream,
# which this class provides.
#
# With default start/end arguments, the scan method generates a single match
# covering the full extent of the token sequence.
# Applying the match coordinator (which applies an extractor within the
# extents of the matches in its input stream) to this match stream thus has
# the same semantics as VRManager performing a scan on the token sequence.
#
# With non-default start/end arguments, it generates a single match with
# the indicated extent. This is the mechanism that allows coordinators to,
# eg, efficiently match within the extent of another coordinator match,
# rather than having to do what they did earlier, which was to overgenerate
# matches using the full token sequence and then drop ones that went beyond
# that extent.
#
# So if there's no further context, _ represents the full extent of the tseq,
# but in a larger context _ may refer to limits establish by surrounding
# context, either by another coordinator, or (conceivably) by explicit
# start/end arguments passed by custom VR code.
#
# For example, in test_match_within_match in test_coordinator.py,
#   noun_coord ~ match(noun, _)
#   noun_in_phrase2 ~ match(noun_coord, noun_phrase)
# where the second expression is equivalent to
#   noun_in_phrase2 ~ match(noun_coord, match(noun_phrase, _))
# the noun_phrase matching is done against the full tseq extents,
# but the noun matching is done against the extents of noun_phrase matches,
# even though '_' is present in both match expressions (implicitly in
# the second one).
# FWIW, the following, using noun directly, gives essentially the same results.
#   noun_in_phrase2 ~ match(noun, match(noun_phrase, _))
#
class BaseCoordinator(Coordinator):
    """Base match stream specified by '_'."""

    def __init__(self, manager: Optional['VRManager'], **kwargs):
        super().__init__(manager, **kwargs)
        self.name = "_"  # experimental; see CoordMatch.__str__

    def scan(self, seq, start=0, end=None, substitutions=None):
        """
        Generates a single match encompassing the full extent of the
        token sequence by default, or the extent indicated by the arguments
        if supplied.
        """
        # if start != 0 or (end is not None and end != len(seq)):  # debug
        #     print("BaseCoordinator.scan called with start=%s, end=%s (i.e., one or both are not defaults)" % (start, end))
        if end is None:
            end = len(seq)
        # TODO? Would make more sense for this to be a CoordMatch,
        # but that requires a positional arg "m".
        # print(f"Yielding _ (base) match for {seq}")
        yield FAMatch(seq=seq, begin=start, end=end, name=self.name)

    def __str__(self):
        return "_"


class FeedCoordinator(Coordinator):
    """
    Base class (only) for Coordinators that have one feed (match source)
    (and a patname).
    """

    def __init__(self, manager: Optional['VRManager'], patname: str, feed, **kwargs):
        super().__init__(manager, **kwargs)
        self.patname = patname
        self.feed = feed

    def requirements(self, substitutions=None):
        return self.feed.requirements(substitutions) | \
               self.manager.requirements(self.patname, substitutions=substitutions)

    def references(self):
        return OrderedSet((self.patname,)) | self.feed.references()


# Note FWIW that only match and select operators generate matches
# with supermatches.
class MatchCoordinator(FeedCoordinator):

    # TODO Document the influence of the start and end params on the behavior.
    def scan(self, seq, start=0, end=None, substitutions=None):
        """
        Generates matches where feed matches *textually* contain matches of the
        given pattern.
        The feed matches become the supermatches of the generated matches.
        """

        # Even though manager.scan will call apply_substitutions, I presume
        # calling it now saves work during the loops below, for efficiency?
        # Similarly, I presume the other assignments here are to save
        # attribute lookup time during the loops?
        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager

        # Adding the fm.end arg to vrm.scan (in addition to the fm.begin
        # param already passed) is the main thing that enables matching
        # only within the bounds of the feed match, and as a result
        # we should no longer really need the pm.end > fm.end check.
        #
        # But adding the end arg to feed.scan is also needed, at least
        # here in the match coordinator, because
        # when vrm.scan calls ext.scan on the extractor for the patname
        # (after having set the seq for the extractor to be fm.seq), we will
        # re-enter a scan method (such as this one) for that extractor.
        #
        # That fm.end arg will end up being the end param of that scan
        # method, and that scan method needs to respect that end value --
        # even if it is the scan method of BaseCoordinator (_).
        #
        # ** In other words, the start and end args to feed.scan provide
        # the context for interpreting the meaning of _, the token subsequence
        # limits that it will be interpreted to encompass.
        #
        # For example, test ~ match(ext2, match(ext1, _)).
        # If ext1 and ext2 are (say) FAs, the FA start/end handling already
        # implements token subsequence limits, so both the vrm.scan calls
        # for both the match coordinators will work fine.
        #
        # But if ext2 ~ match(ext3, _), the vrm.scan call for match(ext2, ...)
        # will call into the scan method for match(ext3, _), and to implement
        # the token subsequence limits, the call to feed.scan for the
        # BaseCoordinator needs to respect the limits.
        #
        for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):  # feed match
            for pm in vrm.scan(patname, fm.seq, fm.begin, fm.end, substitutions=substitutions):  # pattern match
                if pm.end > fm.end:
                    raise GenericException(msg="Pattern match end (%d) exceeds enclosing match end (%d)"
                                               % (pm.end, fm.end))
                # yield DelegatedCoordMatch(pm, op=self, left=fm, submatch=pm, supermatch=fm, name=self.name)
                yield CoordMatch(pm, op=self, left=fm, submatch=pm, supermatch=fm, name=self.name)

    def __str__(self):
        return "MatchCoordinator(%s, %s)" % (self.patname, self.feed)


# Note FWIW that only match and select operators generate matches
# with supermatches.
class SelectCoordinator(FeedCoordinator):

    # Select is a special case of FeedCoordinator where we don't
    # need to explicitly look for requirements of the patname,
    # because we don't explicitly scan on the patname, we only look for
    # previously stored matches of the patname created when running the feed.
    # It's true that that SHOULD involve the patname, but if so it's already
    # covered by the feed requirements.
    def requirements(self, substitutions=None):
        return self.feed.requirements(substitutions)

    def scan(self, seq, start=0, end=None, substitutions=None):
        """
        Generates matches where feed matches contain *already recorded* matches
        of the given pattern within their (recursive) submatches.
        For FAMatch and FAArcMatch this means within the submatches field,
        while for CoordMatch it means within any of the submatch fields:
        submataches, left, right, submatch, supermatch, and (the experimental)
        members.
        The feed matches become the supermatches of the generated matches.
        """
        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed

        # Unfortunately, this check makes it impossible for us to select
        # the slots of frames.
        # If we want to check this, we need a new method on the manager
        # that checks frame slot names.
        # TODO We really should do that, otherwise we'll silently fail
        # to match when a rule name is misspelled, which is bad in itself,
        # and inconsistent with nearly all other cases.
        # if not self.manager.extractor_is_defined(patname):
        #     raise RuntimeError("No such extractor: %s" % patname)

        # TODO See issue #31. Not 100% clear start=0, end=end here is correct,
        # or OTOH if we should have the same in other coordinators besides
        # this one.
        for fm in feed.scan(seq, start=0, end=end, substitutions=substitutions):
            submatches = sorted(fm.all_submatches(patname))
            for pm in submatches:
                if pm.begin >= start and (end is None or pm.end <= end):
                    yield DelegatedCoordMatch(pm, op=self, left=fm, submatch=pm, supermatch=fm, name=self.name)

    def __str__(self):
        return "SelectCoordinator(%s, %s)" % (self.patname, self.feed)


class FilterCoordinator(FeedCoordinator):

    def __init__(self, manager, patname, feed, inverted=False, **kwargs):
        super().__init__(manager, patname, feed, **kwargs)
        self.inverted = inverted

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted

        if inverted:
            # Note that inverted filter matches do not get submatch set.
            # This is the case for all filter-type coordinators.
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                matched = False
                for pm in vrm.scan(patname, fm.seq, fbegin, fend, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    if pend > fend:
                        raise GenericException(msg="Shouldn't happen")
                    matched = True
                    break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                for pm in vrm.scan(patname, fm.seq, fbegin, fend, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    if pend > fend:
                        raise GenericException(msg="Shouldn't happen")
                    # For filter-type coordinators, the new CoordMatch
                    # always has the same extent as the feed match
                    # (or one of them if there are two).
                    yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                    # In addition, filter-type coordinators generate
                    # at most one match for any feed match.
                    break

    def __str__(self):
        return "FilterCoordinator(%s, %d, %s)" % (self.patname, self.inverted, self.feed)


# Note this is the same as Precedes with proximity=0.
# TODO But see Valet issue #32 regarding whether this should be a "filter".
# TODO? It's akin to a filter coordinator in that it takes an inverted flag,
# but it doesn't currently inherit from FilterCoordinator, so the inverted
# flag arg to the ctor is processed by SimpleClass, so we get compiler warnings
# about "unresolved attribute reference". So declare type for now below.
class PrefixFilterCoordinator(FeedCoordinator):
    """
    Matches from stream that have an immediately preceding extractor match.
    """

    inverted: bool

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted

        # The following comments were in the context of before and during
        # while I was converting the scan methods to take an end argument,
        # and converting VRManager.scan to pass it.
        #
        # We have not converted this to use the end arg yet.
        # Does that means that the old implementation below that only
        # yields when diff == 0 is still OK, or are there situations
        # where there is a problem because our caller is expecting
        # feed.scan to respect the end value?
        #
        # Now, since we don't pass any end arg to vrm.scan here yet,
        # it won't be *this* coordinator that would result in end above
        # coming in as non-None.
        # But if some *other* coordinator uses a coordinator of this kind
        # as its patname, and that other coordinator does pass end
        # to fm.scan, then we will get end above coming in as non-None.
        # And we probably don't handle that correctly.
        #
        # Maybe something like this.
        # pat4 ~ prefix(pat1, pat2)
        # pat5 ~ filter(pat4, pat3)
        # where pat1,2,3 could be anything.
        # Pass matches of pat3 for which, within the extent of the pat3 match,
        # there is a match of pat1 prefixing a match of pat2.
        #
        # The documentation has a prefix example.
        # prefix(dollar_sign, 0, match(number, _))
        # pat3 could just be something simple like
        # pat3 -> ( &any+ )
        #
        # I now have a test similar to the above.
        #
        # That test has patterns
        # money ~ prefix(dollar, 0, number)
        # test ~ filter(money, 0, any_in_parens)
        #
        # The filter scan code has been updated to take an end arg, and it
        # passes that to its feed.scan call; feed is match(any_in_parens, _).
        # That's probably fine so far; it's probably coming in as None,
        # and either way both MatchCoordinator and BaseCoordinator know
        # how to handle it.

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                matched = False
                fbegin, _ = fm.get_extent()
                for pm in vrm.scan(patname, fm.seq, start, fbegin, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    diff = fbegin - pend
                    if diff == 0:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, _ = fm.get_extent()
                # TODO Note that Dayne is/was passing start here!
                # That is a different semantics from passing 0,
                # as I'd been expecting to do.
                # Should illustrate that in a test.
                for pm in vrm.scan(patname, fm.seq, start, fbegin, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    diff = fbegin - pend
                    if diff == 0:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                        break  # it's a filter

    def __str__(self):
        return "PrefixFilterCoordinator(%s, %d, %s)" % (
            self.patname, self.inverted, self.feed)


# Note this is the same as follows with proximity=0.
class SuffixFilterCoordinator(FeedCoordinator):
    """
    Matches from stream that have an immediately following extractor match.
    """

    inverted: bool

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                _, fend = fm.get_extent()
                matched = False
                for pm in vrm.scan(patname, fm.seq, fend, end, substitutions=substitutions):
                    pbegin, _ = pm.get_extent()
                    if pbegin == fend:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                _, fend = fm.get_extent()
                # TODO Note that we pass end instead of None;
                # these are two alternate semantics; see Prefix above.
                # Illustrate with a test.
                for pm in vrm.scan(patname, fm.seq, fend, end):
                    pbegin, _ = pm.get_extent()
                    if pbegin == fend:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                        break  # it's a filter

    def __str__(self):
        return "SuffixFilterCoordinator(%s, %d, %s)" % (
            self.patname, self.inverted, self.feed)


# Near just means precedes OR follows, within the given proximity.
class NearFilterCoordinator(FeedCoordinator):

    inverted: bool
    proximity: int

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                matched = False
                for pm in vrm.scan(patname, fm.seq, start, end, substitutions=substitutions):
                    pbegin, pend = pm.get_extent()
                    diff = fbegin - pend
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                    diff = pbegin - fend
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            # I gather this is intended to be identical (as a set of matches)
            # to a union of precedes and follows, but more efficient.
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                for pm in vrm.scan(patname, fm.seq, start, end, substitutions=substitutions):
                    pbegin, pend = pm.get_extent()
                    diff = fbegin - pend
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                    diff = pbegin - fend
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)

    def __str__(self):
        return "NearFilterCoordinator(%s, %d, %d, %s)" % (
            self.patname, self.proximity, self.inverted, self.feed)


class PrecedesFilterCoordinator(FeedCoordinator):

    inverted: bool
    proximity: int

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, _ = fm.get_extent()
                matched = False
                for pm in vrm.scan(patname, fm.seq, start, fbegin, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    diff = fbegin - pend
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, _ = fm.get_extent()
                # TODO Note that we pass start instead of 0.
                # These are two different semantics.
                # Should illustrate that in a test.
                # TODO? If I pass fm.begin-proximity below,
                # I might be able to drop the diff check.
                for pm in vrm.scan(patname, fm.seq, start, fbegin, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    diff = fbegin - pend
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)

    def __str__(self):
        return "PrecedesFilterCoordinator(%s, %d, %d, %s)" % (
            self.patname, self.proximity, self.inverted, self.feed)


class FollowsFilterCoordinator(FeedCoordinator):

    inverted: bool
    proximity: int

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                _, fend = fm.get_extent()
                matched = False
                for pm in vrm.scan(patname, fm.seq, fend, end, substitutions=substitutions):
                    pbegin, _ = pm.get_extent()
                    diff = pbegin - fend
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                _, fend = fm.get_extent()
                # TODO Note that we pass end instead of None;
                # these are two alternate semantics.
                # Illustrate with a test.
                # TODO? If I pass fm.end-proximity below,
                # I might be able to drop the diff check.
                for pm in vrm.scan(patname, fm.seq, fend, end, substitutions=substitutions):
                    pbegin, _ = pm.get_extent()
                    diff = pbegin - fend
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)

    def __str__(self):
        return "FollowsFilterCoordinator(%s, %d, %d, %s)" % (
            self.patname, self.proximity, self.inverted, self.feed)


class CountFilterCoordinator(FeedCoordinator):
    """
    Passes the feed match when there are a given number or more submatches
    of the pattern within the extent of the feed match.
    """

    def scan(self, seq, start=0, end=None, substitutions=None):

        patname = self.manager.apply_substitutions(self.patname, substitutions)
        feed = self.feed
        vrm = self.manager
        inverted = self.inverted
        count = self.count

        if inverted:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                count2 = 0
                for pm in vrm.scan(patname, fm.seq, fbegin, fend, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    if pend <= fend:
                        count2 += 1
                if not count2 >= count:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(seq, start=start, end=end, substitutions=substitutions):
                fbegin, fend = fm.get_extent()
                submatches = []
                for pm in vrm.scan(patname, fm.seq, fbegin, fend, substitutions=substitutions):
                    _, pend = pm.get_extent()
                    if pend <= fend:
                        submatches.append(pm)
                if len(submatches) >= count:
                    m = CoordMatch(fm, op=self, left=fm, submatches=submatches, name=self.name)
                    yield m

    def __str__(self):
        return "CountFilterCoordinator(%s, %d, %d, %s)" % (self.patname, self.count, self.inverted, self.feed)


class TwoFeedCoordinator(Coordinator):
    """
    Base class (only) for Coordinators that have two feeds (match sources).
    """

    def __init__(self, manager, left_feed: Extractor, right_feed: Extractor, **kwargs):
        super().__init__(manager, **kwargs)
        self.left_feed = left_feed
        self.right_feed = right_feed

    def requirements(self, substitutions=None):
        return self.left_feed.requirements(substitutions) | self.right_feed.requirements(substitutions)

    def references(self):
        return self.left_feed.references() | self.right_feed.references()


class NFeedCoordinator(Coordinator):
    """
    Base class for coordinators taking N feeds.
    """

    def __init__(self, manager, feeds: Iterable[Extractor], **kwargs):
        super().__init__(manager, **kwargs)
        self.feeds = feeds

    def requirements(self, substitutions=None):
        req = set()
        for feed in self.feeds:
            req |= feed.requirements(substitutions)
        return req

    def references(self):
        refs = OrderedSet()
        for feed in self.feeds:
            refs |= feed.references()
        return refs

    def accumulate(self, match, result, require_existing=False):
        """
        Continue to accumulate data from each incoming "match" into "result",
        which is keyed by match extent.
        Coextensive matches are unified into a single "result" entry,
        accumulating the matches into the submatches list.
        Coextensive matches that are or represent frames also have their
        frame fields merged.
        """
        try:
            om = result[match]  # om = original match
            m_frame = match.get_frame()
            om_frame = om.get_frame()
            if m_frame and not om_frame:
                # This is the first frame we have encountered for this extent.
                submatches = result[match].submatches + [match]
                # This will replace a result[match] created earlier by the KeyError clause below.
                # The new CoordMatch.match now gives us a place to store the merged frames when we call set_frame.
                tmp = CoordMatch(match, op=self, name=self.name, submatches=submatches)
                result[match] = tmp
                # print(f"Replaced ... ")
            else:
                om.submatches.append(match)
                if m_frame and om_frame:
                    merged_frame = om_frame.merge(m_frame)
                    # print(f"NFeedCoordinator.accumulate merged frame {hex(id(om_frame))} and {hex(id(m_frame))} giving {hex(id(merged_frame))}")
                    # set_frame avoids overwriting the frame within
                    # a .match field accessible via a cached CoordMatch
                    # in the chain of CoordMatch'es leading to the frame
                    # via their .match fields.
                    # It copies the entire chain of CoordMatches,
                    # except for the one created in the present method.
                    result[match] = om.set_frame(merged_frame)
        except KeyError:
            if not require_existing:
                result[match] = CoordMatch(match, op=self, name=self.name, submatches=[match])
            # else caller (intersection) will handle doing del result[match] if needed.
            # It's sufficient for intersection that we don't set result[match] here.


class JoinCoordinator(TwoFeedCoordinator):
    """
    Base class (only) for two-feed coordinators that are interested in
    various kinds of overlaps of their two feeds.
    """

    # Generates all overlapping matches between two streams
    # TODO: Deprecate and remove once 'scan' replaces 'matches'
    def _generate_overlaps(self, seq, include_non_overlaps=False):

        rightm = list(self.right_feed.matches(seq))

        def overlaps(lm, rm):
            return (lm.begin <= rm.begin < lm.end or
                    lm.begin < rm.end <= lm.end or
                    rm.begin <= lm.begin < rm.end or
                    rm.begin < lm.end <= rm.end)

        for lm in self.left_feed.matches(seq):
            for rm in (m for m in rightm if overlaps(lm, m)):
                yield lm, rm

    def _generate_overlaps_scan(self, seq, start=0, end=None, substitutions=None):

        rightm = list(self.right_feed.scan(seq, start=start, end=end, substitutions=substitutions))

        for lm in self.left_feed.scan(seq, start=start, end=end, substitutions=substitutions):
            for rm in (m for m in rightm if lm.overlaps(m)):
                yield lm, rm


class OverlapCoordinator(JoinCoordinator):
    """
    Matches in the left stream that overlap with some match in the right stream.
    """

    def scan(self, seq, start=0, end=None, substitutions=None):
        for lm, rm in self._generate_overlaps_scan(seq, start=start, end=end, substitutions=substitutions):
            yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)

    def __str__(self):
        return "OverlapCoordinator(%s, %s)" % (self.left_feed, self.right_feed.__str__())


class ContainCoordinator(JoinCoordinator):
    """
    Matches in the left stream that contain some match in the right stream.
    """

    def scan(self, seq, start=0, end=None, substitutions=None):
        for lm, rm in self._generate_overlaps_scan(seq, start=start, end=end, substitutions=substitutions):
            if lm.covers(*rm.get_extent()):
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)

    def __str__(self):
        return "ContainCoordinator(%s, %s)" % (self.left_feed, self.right_feed)


# Consider removing this operator, since there are already several ways
# of achieving the same effect.
# contained_by(b, a)
# match(b, a)
# select(b, contains(a, b))
# (If the desired b is an expression, one can use that expression
# to define a named pattern, and the name can then be used in match
# or select.)
class ContainedByCoordinator(JoinCoordinator):
    """
    Matches in the left stream that are contained by some match in the right stream.
    """

    def matches_deprecated(self, seq):
        raise NotImplementedError()

        lastm = None
        for lm, rm in self._generate_overlaps(seq):
            if rm.begin <= lm.begin and lm.end <= rm.end:
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                # if lm is not lastm:
                #     yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                lastm = lm

    def scan(self, seq, start=0, end=None, substitutions=None):
        lastm = None
        for lm, rm in self._generate_overlaps_scan(seq, start=start, end=end, substitutions=substitutions):
            if rm.begin <= lm.begin and lm.end <= rm.end:
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                # if lm is not lastm:
                #     yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                lastm = lm

    def __str__(self):
        return "ContainedByCoordinator(%s, %s)" % (self.left_feed, self.right_feed)


class IntersectionCoordinator(NFeedCoordinator):
    """
    Matches in the leftmost stream that are coextensive in all the streams.
    """

    def scan(self, seq, start=0, end=None, substitutions=None):
        result = None
        for feed in self.feeds:
            matches = feed.scan(seq, start=start, end=end, substitutions=substitutions)
            if result is None:  # first feed
                # Set up initial results to accumulate into.
                result = {}
                for m in matches:
                    try:
                        result[m].submatches.append(m)
                    except KeyError:
                        result[m] = CoordMatch(m, op=self, name=self.name, submatches=[m])
            else:  # subsequent feeds
                # Accumulate, but only on top of "existing" results
                # for which all previous feeds contained that extent.
                matched = set()
                for m in matches:
                    self.accumulate(m, result, require_existing=True)
                    matched.add(m)
                # Delete accumulated results where all previous feeds
                # had that extent, but this feed didn't.
                for rm in list(result.keys()):
                    if rm not in matched:
                        del result[rm]
            if len(result) == 0:
                # No need to go through remaining feeds.
                return
        for m in result.values():
            m.normalize_endpoints()
            yield m

    def __str__(self):
        return "IntersectionCoordinator(%s)" % ", ".join(str(feed) for feed in self.feeds)


class UnionCoordinator(NFeedCoordinator):
    """
    Return all matches from the N streams.
    Any matches having the same extent produce a single match in the output.
    """

    def scan(self, seq, start=0, end=None, substitutions=None):
        result = {}
        for feed in self.feeds:
            matches = feed.scan(seq, start=start, end=end, substitutions=substitutions)
            for m in matches:
                self.accumulate(m, result)
        for m in result.values():
            m.normalize_endpoints()
            yield m

    def __str__(self):
        return "UnionCoordinator(%s)" % ", ".join(str(feed) for feed in self.feeds)


class DiffCoordinator(NFeedCoordinator):
    """
    Return any matches in the first stream not found in any of the subsequent
    streams (that is, matches in the first stream for which there is no match
    in any of the subsequent streams with the same extent).
    """

    def scan(self, seq, start=0, end=None, substitutions=None):
        result = None
        for feed in self.feeds:
            matches = list(feed.scan(seq, start=start, end=end, substitutions=substitutions))
            if result is None:  # first feed
                # Set up initial results from first feed.
                result = {}
                for m in matches:
                    try:
                        result[m].submatches.append(m)
                    except KeyError:
                        result[m] = CoordMatch(m, op=self, name=self.name, submatches=[m])
            else:  # subsequent feeds
                # Remove any that came from first feed that have same extent
                # as one in this feed.
                for m in matches:
                    if m in result:
                        del result[m]
            if len(result) == 0:
                # No need to go through remaining feeds.
                return
        for m in result.values():
            m.normalize_endpoints()
            yield m

    def __str__(self):
        return "DiffCoordinator(%s)" % ", ".join(str(feed) for feed in self.feeds)


class ConnectsCoordinator(JoinCoordinator):
    """
    Produces matches based on two feeds and a (usually parse) pattern name,
    producing a match whenever a pair of matches from the feeds is connected
    by the given parse tree path relationship (more specifically, if the
    named pattern match overlaps with both feed pattern matches).
    """

    def __init__(self, manager, left_feed, right_feed, patname, **kwargs):
        super().__init__(manager, left_feed, right_feed, **kwargs)
        self.patname = patname

    def requirements(self, substitutions=None):
        return super().requirements(substitutions) | \
            self.manager.requirements(self.patname, substitutions=substitutions)

    def references(self):
        return OrderedSet((self.patname,)) | super().references()

    # Does it make sense to use the same start/end for two different feeds?
    # I guess what that means is that we're using the same token subsequence
    # for interpreting _ when this connects coordinator is used as the
    # extractor of another coordinator.
    def scan(self, seq, start=0, end=None, substitutions=None):
        leftm = list(self.left_feed.scan(seq, start=start, end=end, substitutions=substitutions))
        if len(leftm) == 0:
            return
        rightm = list(self.right_feed.scan(seq, start=start, end=end, substitutions=substitutions))
        if len(rightm) == 0:
            return
        for lm in leftm:
            s, e = lm.get_extent()
            for i in range(s, e):
                # We use the matches() method to ensure that all matches start
                # at the indicated index.
                # TODO Here and elsewhere, should we just use the passed-in seq?
                # Doesn't matter much, but probably better.
                for pm in self.manager.matches(self.patname, lm.seq, start=i, substitutions=substitutions):
                    hits = [rm for rm in rightm if rm.covers(pm.end)]
                    for rm in hits:
                        yield DelegatedCoordMatch(pm, op=self, left=lm, right=rm, submatch=pm, name=self.name)

    def __str__(self):
        patname = self.patname
        lf = self.left_feed
        rf = self.right_feed
        return "ConnectsCoordinator(%s, %s, %s)" % (patname, lf, rf)


# This operator is deprecated.
# What did it do? Is it replaced by connects()?
class HasPathFilterCoordinator(JoinCoordinator):

    # Generates all overlapping matches between two streams
    def _generate_connections(self, seq):
        # print(self.manager)
        left = list(self.left_feed.matches(seq))
        right = list(self.right_feed.matches(seq))
        dpath = self.dpath

        for lm, rm in self._generate_sequence_connections(left, right, dpath):
            yield lm, rm

    def _generate_sequence_connections(self, leftm, rightm, dpath):
        llen = len(leftm)
        rlen = len(rightm)

        def connects(seq, li, ri, dpath):
            # print("DPATH: %s" %dpath)
            lm = leftm[li]
            rm = rightm[ri]
            # TODO Anytime .begin/end are used with range(),
            # almost definitely need to call get_extent().
            for i in range(lm.begin, lm.end):
                for j in range(rm.begin, rm.end):
                    if dpath in seq.find_paths(i, j):
                        return True
            return False

        for li in range(llen):
            for ri in range(rlen):
                if connects(leftm[li].seq, li, ri, dpath):
                    yield leftm[li], rightm[ri]

    def matches_deprecated(self):
        raise NotImplementedError()

    def scan(self, seq, start=0, end=None, substitution=None):
        """
        This operator is deprecated.
        """
        raise NotImplementedError()

    def __str__(self):
        lf = self.left_feed
        rf = self.right_feed
        dp = self.dpath
        return "HasPathFilterCoordinator(%s, %s, %s)" % (lf, rf, dp)


# Dayne's motivating example:
# symptom ~ when(symptom_header and not medications_header,
#                overly_general_pattern)
class WhenCoordinator(Coordinator):
    """
    Produces matches based on a feed and a boolean expression over pattern
    names, producing a match whenever a match from the feed is produced
    and the boolean expression is satisfied.
    The boolean expression is considered satisfied according to whether there
    have been matches or a lack of matches of those named patterns earlier
    in the same "document", in previous tseqs. I.e., any earlier match of
    a named pattern is considered true, and no matches is considered false.
    """

    def __init__(self, manager, boolean: 'WhenHandler', feed, **kwargs):
        super().__init__(manager, **kwargs)
        self.boolean = boolean
        self.feed = feed

    # In scan, I'll need to first "evaluate" the boolean expression.
    # If that turns out true, I can scan the feed.
    # Or I might need to do that ANYWAY in case the FEED ITSELF
    # contains a boolean expression somewhere, perhaps even just inside
    # a referenced rule.
    # I say that because you'd probably want the referenced patnames
    # of the referenced rule to be "evaluated".
    # I think I want to always scan the feed.
    #
    # To "evaluate", I need to check the manager for each atom rule's
    # flag state BEFORE the current tseq.
    # But I probably somehow need to also RUN those atom rules on the
    # current tseq AFTER that to UPDATE their values for the benefit
    # of SUBSEQUENT tseqs.
    #
    # However, there's a TIMING ISSUE.
    # The current rule (eg "symptom" in Dayne's example)
    # might be REFERENCED as part of a LARGER RULE.
    # If that ALSO mentions some of the atom rules, then the flag state
    # for those might ALREADY HAVE BEEN UPDATED.
    #
    # Perhaps it would be sufficient to check whether the current tseq
    # is the ONLY ONE for which the flag state is true.
    # Eg, we'd do like I speculated and keep a list or SET of the tseqs
    # as the state, not just a single boolean value.
    #
    # TODO? Separately, you might want to be able to EXTERNALIZE
    # the boolean expr, moving it OUTSIDE the when() expr into ITS OWN RULE.
    # Wouldn't need that initially, though.

    def scan(self, seq, start=0, end=None, substitutions=None):

        # Check whether condition is true for PAST tseqs.
        # TODO? Do we want to make matches from referenced patterns
        # SUBMATCHES of any matches that we return?
        # For now I'm going to table that.
        status: bool = self.boolean.evaluate(seq)

        # Record rule ATOMs' statuses for CURRENT tseq.
        self.boolean.record(seq)

        # Scan the feed regardless of the status, in case it involves
        # when() coordinators for which we want to record status.
        leftm = list(self.feed.scan(seq, start=start, end=end, substitutions=substitutions))
        if not status or len(leftm) == 0:
            return
        for lm in leftm:
            yield CoordMatch(lm, op=self, left=lm, name=self.name)  # submatches=?

    def requirements(self, substitutions=None):
        req = self.feed.requirements(substitutions)
        for patname in self.boolean.all_patnames():
            req |= self.manager.requirements(patname, substitutions=substitutions)
        return req

    def references(self):
        refs = OrderedSet(self.boolean.all_patnames()) | self.feed.references()
        return refs

    def __str__(self):
        boolean = self.boolean
        feed = self.feed
        return "WhenCoordinator(%s, %s)" % (boolean, feed)


# TODO Is this still valid?
class WidenCoordinator(FeedCoordinator):
    """
    For coordination matches that select matches from one of their
    input streams, this produces matches that covers the extent
    of both (?) matches and intervening text.
    """

    def references(self):
        return self.feed.references()

    def scan(self, seq, start=0, end=None, substitutions=None):
        feed = self.feed
        for m in feed.scan(seq, start=start, end=end, substitutions=substitutions):
            yield m.widen()

    def __str__(self):
        return "WidenCoordinator(%s)" % self.feed


# This operator is deprecated.
# Appears to have something to do with merging consecutive overlapping
# matches within a single feed.
class MergeCoordinator(FeedCoordinator):

    def matches_deprecated(self, seq):
        raise NotImplementedError()

        ms = sorted(list(self.feed.matches(seq)))
        last_match = None
        for m in ms:
            if last_match is None:
                last_match = CoordMatch(m, op=self, left=m, name=self.name, members=[m])
            elif last_match.overlaps(m):
                if m.begin < last_match.begin:
                    last_match.begin = m.begin
                if m.end > last_match.end:
                    last_match.end = m.end
                last_match.members.append(m)
            else:
                yield last_match
                last_match = CoordMatch(m, op=self, left=m, name=self.name, members=[m])
        if last_match is not None:
            yield last_match

    def scan(self, seq, start=0, end=None, substitutions=None):
        """
        Maybe deprecate this operator.  I don't understand its intended use.
        """
        raise NotImplementedError()

    def __str__(self):
        return "MergeCoordinator(%s)" % self.feed


###############################################################################


# NOTE: As with selects and Frame queries, there are potential issues
# regarding recording and retrieval of dotted pattern names.
# See comments at query_name_matches() in match.py.
class WhenHandler(SimpleClass):
    """A new kind of object supporting WhenCoordinator, implementing the
    semantics associated with the boolean expression in the cooordinator."""

    cached_patnames: Optional[Iterable[str]]  # result from all_patnames()
    cached_str: Optional[str]  # result from __str__()

    def __init__(self, manager: 'VRManager', **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        self.cached_patnames = None
        self.cached_str = None

    @abstractmethod
    def evaluate(self, tseq: TokenSequence) -> bool:
        """Calculate the boolean value of the expression, based on info
        recorded in the manager about which rules matched previous tseqs."""
        pass

    # Where this bottoms out in RefHandler, we do a scan for the referenced
    # pattern, so we're not just RECORDING match status, we're DETERMINING
    # status.
    # For the scan, we don't need start/end params, as we want to record
    # matches anywhere in the tseq, not just within the current start/end.
    @abstractmethod
    def record(self, tseq: TokenSequence, substitutions=None) -> None:
        """Determine and record the match status of individual patterns
        in the boolean expression relative to the current tseq."""
        pass

    @abstractmethod
    def all_patnames(self) -> Iterable[str]:
        """All patnames referenced by the boolean expression."""
        pass


class OrHandler(WhenHandler):
    subs: Iterable[WhenHandler]  # at least 2

    def evaluate(self, tseq: TokenSequence) -> bool:
        for sub in self.subs:  # may short ciruit
            if sub.evaluate(tseq):
                return True
        return False

    def record(self, tseq: TokenSequence, substitutions=None) -> None:
        for sub in self.subs:  # no short circuit
            sub.record(tseq, substitutions=substitutions)

    def all_patnames(self) -> Iterable[str]:
        if self.cached_patnames is None:
            self.cached_patnames = OrderedSet(
                    chain.from_iterable(sub.all_patnames() for sub in self.subs))
        return self.cached_patnames

    def __str__(self):
        if self.cached_str is None:
            self.cached_str = " or ".join(str(sub) for sub in self.subs)
        return self.cached_str


class AndHandler(WhenHandler):
    subs: Iterable[WhenHandler]  # at least 2

    def evaluate(self, tseq: TokenSequence) -> bool:
        for sub in self.subs:
            if not sub.evaluate(tseq):
                return False
        return True

    def record(self, tseq: TokenSequence, substitutions=None) -> None:
        for sub in self.subs:
            sub.record(tseq, substitutions=substitutions)

    def all_patnames(self) -> Iterable[str]:
        if self.cached_patnames is None:
            self.cached_patnames = OrderedSet(
                    chain.from_iterable(sub.all_patnames() for sub in self.subs))
        return self.cached_patnames

    def __str__(self):
        if self.cached_str is None:
            self.cached_str = " and ".join(str(sub) if isinstance(sub, NotHandler) or isinstance(sub, RefHandler)
                                           else f"({sub})"
                                           for sub in self.subs)
        return self.cached_str


class NotHandler(WhenHandler):
    arg: WhenHandler

    def evaluate(self, tseq: TokenSequence) -> bool:
        return not self.arg.evaluate(tseq)

    def record(self, tseq: TokenSequence, substitutions=None) -> None:
        self.arg.record(tseq, substitutions=substitutions)

    def all_patnames(self) -> Iterable[str]:
        if self.cached_patnames is None:
            self.cached_patnames = self.arg.all_patnames()
        return self.cached_patnames

    def __str__(self):
        if self.cached_str is None:
            if isinstance(self.arg, RefHandler):
                self.cached_str =  f"not {str(self.arg)}"
            else:
                self.cached_str =  f"not ({str(self.arg)})"
        return self.cached_str


class RefHandler(WhenHandler):
    patname: str

    def evaluate(self, tseq: TokenSequence) -> bool:
        return self.manager.recorded(self.patname, tseq)

    def record(self, tseq: TokenSequence, substitutions=None) -> None:
        for match in self.manager.scan(self.patname, tseq, substitutions=substitutions):
            # The manager may have applied substitutions to our patname,
            # so get the actual patname used from the match and record that.
            if not hasattr(match, "name") or match.name is None:
                raise Exception(f"Unexpected: match {match} was not assigned a name")
            self.manager.record(match.name, tseq)
            # _logger.debug("Recording match of '%s' for tseq '%s'" % (match.name, tseq.tokens))
            # TODO? We don't need to record tseq more than once, but we might
            # want to track all matches and make them submatches of any matches
            # the WhenCoordinator generates for matches from its feed?
            break

    def all_patnames(self) -> Iterable[str]:
        if self.cached_patnames is None:
            self.cached_patnames = [self.patname]
        return self.cached_patnames

    def __str__(self):
        return self.patname
