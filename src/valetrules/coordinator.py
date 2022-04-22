from abc import abstractmethod
import functools

from nlpcore.dbfutil import SimpleClass, GenericException

from .match import FAMatch, CoordMatch

"""
Provides the Coordinator base class and numerous subclasses largely 
mirroring the taxonomy of coordinator expressions -- MatchCoordinator, 
SelectCoordinator, FilterCoordinator, OverlapsCoordinator, etc.
Coordinator expressions are parsed by the coordinatorexp module into 
a tree of Coordinator instances mirroring the structure of the expression.
"""

# TODO? All the coordinators still directly reference match.begin/end, 
# rather than calling match.get_begin_end. 
# There's a good chance that implies bugs if the match class is unknown 
# (so multiple possible conventions) or if there are reversed indices. 

# TODO? Note that in practice none of the coordinators are assigned 
# name attributes (except for None in Coordinator.__init__), 
# so the coordinators passing self.name to all the match objects 
# they create does not have any real effect. 
# (I.e., just as well to set to None in match __init__ methods.)
#
# [I did see at least one exception to the above, so need further 
# investigation.]
#
# Most match objects have their name assigned in VRManager._scan, 
# and ones that don't are ones associated with internal subexpressions 
# of named expressions, which don't get to that _scan method to get named.

# TODO The matches methods are probably obsolete. Once we're sure, drop them.

class Coordinator(SimpleClass):
    """Base class for other coordinators."""

    def __init__(self, **args):
        super().__init__(**args)
        if not hasattr(self, 'name'):
            self.name = None

    def set_source_sequence(self, sequence):
        self.sequence = sequence

    def get_source_sequence(self):
        return self.sequence

    def matches(self, sequence, start=0, end=None, bounds=None):
        """Matches only yields matches anchored at the indicated start position"""
        self.set_source_sequence(sequence)
        for m in self.scan(start=start, end=end):
            if m.begin == start:
                yield m

    def requirements(self):
        return set()

    @abstractmethod
    def scan(self, start=0, end=None):
        raise NotImplementedError()


# "Base" here indicates base stream, not base class.
# The coordinators take match streams as input and produce match streams 
# as output, so we need to have a way of producing an initial match stream, 
# which this class provides. 
#
# It returns a single match covering the full extent of the token sequence.
# Applying the match coordinator (which applies an extractor within the 
# extents of the matches in its input stream) to this match stream thus has 
# the same semantics as VRManager performing a scan on the token sequence.
#
# With non-default start/end arguments, it returns a single match with 
# the indicated extent. This is the mechanism that allows coordinators to, 
# eg, match within the extent of another coordinator match, rather than 
# having to do what they did earlier, which is to overgenerate matches 
# and then drop ones that went beyond that extent.
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
# but the noun matching is done against the extents of noun_phrase matching, 
# even though '_' is present in both match expressions (implicitly in 
# the second one).
#
class BaseCoordinator(Coordinator):
    """Base match stream specified by '_'."""

    def __init__(self, **args):
        super().__init__(**args)
        self.name = "_"  # experimental; see CoordMatch.__str__

    def scan(self, start=0, end=None):
        """
        Generates a single match encompassing the full extent of the 
        input string by default, or the extent indicated by the arguments 
        if supplied.
        """
        seq = self.get_source_sequence()
        # if start != 0 or end is not None:
        #     print("BaseCoordinator.scan called with start=%s, end=%s (i.e., one or both are not defaults)" % (start, end))
        if end is None:
            end = len(seq)
        # TODO? Would make more sense for this to be a CoordMatch, 
        # but that requires a positional arg "m".
        yield FAMatch(seq=seq, begin=start, end=end, name=self.name)

    def __str__(self):
        return "_"


class FeedCoordinator(Coordinator):
    """
    Base class (only) for Coordinators that have one feed (match source).
    """

    # TODO? What was I going to do with this?
    # I guess specify the more important args explicitly and not have them 
    # handled by SimpleClass.
    # def __init__(parent, patname, feed):

    def set_source_sequence(self, sequence):
        self.feed.set_source_sequence(sequence)

    def get_source_sequence(self):
        return self.feed.get_source_sequence()

    def requirements(self):
        patname = self.patname
        feed = self.feed
        fam = self.parent
        return feed.requirements() | fam.requirements(patname)

    @abstractmethod
    def scan(self, start=0, end=None):
        raise NotImplementedError()


# Note FWIW that only match and select operators generate matches 
# with supermatches.
class MatchCoordinator(FeedCoordinator):

    # TODO Document the influence of the start and end params on the behavior.
    def scan(self, start=0, end=None):
        """
        Generates matches where feed matches *textually* contain matches of the
        given pattern.
        The feed matches become the supermatches of the generated matches.
        """
        patname = self.patname
        feed = self.feed
        fam = self.parent

        # Adding the fm.end arg to fam.scan (in addition to the fm.begin 
        # param already passed) is the main thing that enables matching 
        # only within the bounds of the feed match, and as a result 
        # we no longer really need the pm.end > fm.end check.
        #
        # But adding the end arg to feed.scan is also needed, at least 
        # here in the match coordinator, because 
        # when fam.scan calls ext.scan on the extractor for the patname
        # (after having set the seq for the extractor to be fm.seq), we will 
        # re-enter a scan method (such as this one) for that extractor.
        #
        # That fm.end arg will end up being the end param of that scan 
        # method, and that scan method needs to respect that end value --
        # even if it is the scan method of BaseCoordinator (_).
        #
        # ** In other words, the start and end args to feed.scan provide 
        # the context for interpreting the meaning of _, the toke subsequence 
        # limits that it will be interpreted to encompass.
        #
        # For example, test ~ match(ext2, match(ext1, _)).
        # If ext1 and ext2 are (say) FAs, the FA start/end handling already 
        # implements token subsequence limits, so both the fam.scan calls 
        # for both the match coordinators will work fine.
        #
        # But if ext2 ~ match(ext3, _), the fam.scan call for match(ext2, ...)
        # will call into the scan method for match(ext3, _), and to implement 
        # the token subsequence limits, the call to feed.scan for the 
        # BaseCoordinator needs to respect the limits.
        #
        for fm in feed.scan(start=start, end=end):  # feed match
            for pm in fam.scan(patname, fm.seq, fm.begin, fm.end):  # pattern match
                # Note that because scanning provides no guarantees about the order in which matches are
                # generated, breaking (as in matches()) is not appropriate.
                # TODO Was that just wrong in matches(), or did introducing 
                # the start parameter somehow make it wrong?
                # (These comments are in the context of the previous code 
                # where we had a continue here, vs the break in matches().)
                if pm.end > fm.end:
                    raise GenericException(msg="Shouldn't happen")
                yield CoordMatch(pm, op=self, left=fm, submatch=pm, supermatch=fm, name=self.name)

    def __str__(self):
        return "MatchCoordinator(%s, %s)" % (self.patname, self.feed)


# Note FWIW that only match and select operators generate matches 
# with supermatches.
class SelectCoordinator(FeedCoordinator):

    def scan(self, start=0, end=None):
        """
        Generates matches where feed matches contain *recorded* matches of the
        given pattern within their (recursive) submatches.
        For FAMatch this means within the submatches field, while for
        CoordMatch it means within the left, right, submatch, and supermatch
        fields.
        The feed matches become the supermatches of the generated matches.
        """
        patname = self.patname
        feed = self.feed

        if not self.parent.extractor_is_defined(self.patname):
            raise RuntimeError("No such extractor: %s" % self.patname)

        for fm in feed.scan(start=start, end=end):
            submatches = sorted(fm.all_submatches(patname))
            for pm in submatches:
                yield CoordMatch(pm, op=self, left=fm, submatch=pm, supermatch=fm, name=self.name)

    def __str__(self):
        return "SelectCoordinator(%s, %s)" % (self.patname, self.feed)


class FilterCoordinator(FeedCoordinator):

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted

        if inverted:
            # Note that inverted filter matches do not get submatch set.
            # This is the case for all filter-type coordinators.
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, fm.begin, fm.end):
                    if pm.end > fm.end:
                        raise GenericException(msg="Shouldn't happen")
                    matched = True
                    break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                for pm in fam.scan(patname, fm.seq, fm.begin, fm.end):
                    if pm.end > fm.end:
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
class PrefixFilterCoordinator(FeedCoordinator):
    """
    Matches from stream that have an immediately preceding extractor match.
    """

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
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
        # Now, since we don't pass any end arg to fam.scan here yet, 
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
        # TODO Yet would that situation have not worked before? 
        # Or would it just have been less efficient?
        # Or would it have simply *never happened*?
        # And if not, it seems we have a new situation / capability 
        # that *we need to make sure works correctly now*.
        #
        # I think it's the *last of those*.
        # We never used to allow passing in end above, 
        # That means we never needed to limit the extent of the feed.scan 
        # call before. 
        # The main time that happens now is when *some other coordinator 
        # uses this coordinator as its patname*. 
        # Yet, it could have done so previously as well, and AFAIK that 
        # should and would have worked.
        #
        # I now have a test similar to the above, and the test works 
        # with the old code, but with the new code it ran into the 
        # NotImplementedError here.
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
        #
        # * The filter is also now passing the fm.end value (from the 
        # any_in_parens match) as end to the present coordinator (via 
        # VRManager), and that's where we run into this NotImplementedError.
        #
        # * So it seems that these end args are kind of "viral", 
        # at least to some degree.
        # The next question is how viral.
        #
        # * I think that as an intermediate step short of complete conversion 
        # to pass along the end arg, it should be possible to modify 
        # coordinators like the present one to respect the end arg, 
        # without otherwise modifying the code to pass along end args.
        #
        # * Basically, I think we can just drop fm's for which fm.end > end.
        # That does let the test pass.
        #
        # What about compensating for not passing an end arg to fam.scan?
        # I don't there's any compensation needed.
        # If it worked before, it should still work now.
        #
        # But there's probably now an opportunity to pass an end arg to the 
        # fam.scan call to improve the efficiency, either as part of the 
        # complete conversion, or even separately.
        #
        # But for the feed.scan calls, is there any reason why we shouldn't 
        # just start passing end=end now everywhere? I can't think of one. 
        # Unless we run into any coordinators with special situations, 
        # we should be able to do that now, and come back to the fam.scan 
        # calls later.
        #
        # Going ahead with that plan.
        #
        # TODO Well, but am I sure that just passing end=end is sufficient?
        # I need to be sure that all the feeds can act on it appropriately.
        # All feeds will bottom out in the BaseCoordinator, and I've already 
        # updated that. So I'm probably OK.

        if inverted:
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, start, fm.begin):
                    diff = fm.begin - pm.end
                    if diff == 0:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                # TODO Note that Dayne is/was passing start here!
                # That is a different semantics from passing 0, 
                # as I'd been expecting to do.
                # Should illustrate that in a test.
                for pm in fam.scan(patname, fm.seq, start, fm.begin):
                    diff = fm.begin - pm.end
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

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted

        if inverted:
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, fm.end, end):
                    if pm.begin == fm.end:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                # TODO Note that we pass end instead of None; 
                # these are two alternate semantics.
                # Illustrate with a test.
                for pm in fam.scan(patname, fm.seq, fm.end, end):
                    if pm.begin == fm.end:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                        break  # it's a filter

    def __str__(self):
        return "SuffixFilterCoordinator(%s, %d, %s)" % (
            self.patname, self.inverted, self.feed)


# Near just means precedes OR follows, within the given proximity.
class NearFilterCoordinator(FeedCoordinator):

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, start, end):
                    diff = fm.begin - pm.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                    diff = pm.begin - fm.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            # I gather this is intended to be identical (as a set of matches) 
            # to a union of precedes and follows, but more efficient.
            for fm in feed.scan(start=start, end=end):
                for pm in fam.scan(patname, fm.seq, start, end):
                    diff = fm.begin - pm.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)
                    diff = pm.begin - fm.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)

    def __str__(self):
        return "NearFilterCoordinator(%s, %d, %d, %s)" % (
            self.patname, self.proximity, self.inverted, self.feed)


class PrecedesFilterCoordinator(FeedCoordinator):

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, start, fm.begin):
                    diff = fm.begin - pm.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                # TODO Note that we pass start instead of 0.
                # These are two different semantics.
                # Should illustrate that in a test.
                # TODO? If I pass fm.begin-proximity below, 
                # I might be able to drop the diff check.
                for pm in fam.scan(patname, fm.seq, start, fm.begin):
                    diff = fm.begin - pm.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(fm, op=self, left=fm, submatch=pm, name=self.name)

    def __str__(self):
        return "PrecedesFilterCoordinator(%s, %d, %d, %s)" % (
            self.patname, self.proximity, self.inverted, self.feed)


class FollowsFilterCoordinator(FeedCoordinator):

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for fm in feed.scan(start=start, end=end):
                matched = False
                for pm in fam.scan(patname, fm.seq, fm.end, end):
                    diff = pm.begin - fm.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                # TODO Note that we pass end instead of None; 
                # these are two alternate semantics.
                # Illustrate with a test.
                # TODO? If I pass fm.end-proximity below, 
                # I might be able to drop the diff check.
                for pm in fam.scan(patname, fm.seq, fm.end, end):
                    diff = pm.begin - fm.end
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

    def scan(self, start=0, end=None):

        patname = self.patname
        feed = self.feed
        fam = self.parent
        inverted = self.inverted
        count = self.count

        if inverted:
            for fm in feed.scan(start=start, end=end):
                count2 = 0
                for pm in fam.scan(patname, fm.seq, fm.begin, fm.end):
                    if pm.end <= fm.end:
                        count2 += 1
                if not count2 >= count:
                    yield CoordMatch(fm, op=self, left=fm, name=self.name)
        else:
            for fm in feed.scan(start=start, end=end):
                submatches = []
                for pm in fam.scan(patname, fm.seq, fm.begin, fm.end):
                    if pm.end <= fm.end:
                        submatches.append(pm)
                if len(submatches) >= count:
                    yield CoordMatch(fm, op=self, left=fm, submatches=submatches, name=self.name)

    def __str__(self):
        return "CountFilterCoordinator(%s, %d, %d, %s)" % (self.patname, self.count, self.inverted, self.feed)


class TwoFeedCoordinator(Coordinator):
    """
    Base class (only) for Coordinators that have two feeds (match sources).
    """

    def set_source_sequence(self, sequence):
        self.left_feed.set_source_sequence(sequence)
        self.right_feed.set_source_sequence(sequence)

    # Both feeds are given the same sequence, so we can retrieve it from 
    # either one.
    def get_source_sequence(self):
        return self.left_feed.get_source_sequence()

    def requirements(self):
        return self.left_feed.requirements() | self.right_feed.requirements()

    @abstractmethod
    def scan(self, start=0, end=None):
        raise NotImplementedError()


class NFeedCoordinator(Coordinator):
    """
    Base class for coordinators taking N feeds.
    """

    def set_source_sequence(self, sequence):
        for feed in self.feeds:
            feed.set_source_sequence(sequence)

    def get_source_sequence(self):
        return self.feeds[0].get_source_sequence()

    def requirements(self):
        req = set()
        for feed in self.feeds:
            req |= feed.requirements()
        return req

    @abstractmethod
    def scan(self, start=0, end=None):
        raise NotImplementedError()


# TODO: Make the coordinators that these 'S' coordinators emulate behave like 
# the 'S' coordinators.
# They were basically introduced to allow arbitrary coordinator expressions 
# in places where the corresponding coordinator only allows named extractors. 
# Since we already allow extractor names in contexts where we previously
# required coordinator expressions, we should generalize in the other 
# direction too, allowing expressions where only names are currently permitted.


class SNearFilterCoordinator(TwoFeedCoordinator):

    def matches_deprecated(self):
        raise NotImplementedError()

        left_feed = self.left_feed
        right_feed = self.right_feed
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for m in right_feed.matches():
                matched = False
                for m2 in left_feed.matches():
                    diff = m.begin - m2.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                    diff = m2.begin - m.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(m, op=self, left=m, name=self.name)
        else:
            for m in right_feed.matches():
                for m2 in left_feed.matches():
                    diff = m.begin - m2.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(m, op=self, left=m, submatch=m2, name=self.name)
                        break
                    diff = m2.begin - m.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(m, op=self, left=m, submatch=m2, name=self.name)
                        break

    def scan(self, start=0, end=None):
        """
        This operator is deprecated.
        """
        raise NotImplementedError()

    def __str__(self):
        return "SNearFilterCoordinator(%s, %d, %d, %s, %s)" % (
            self.patname, self.proximity, self.inverted, self.left_feed, self.right_feed)


class SPrecedesFilterCoordinator(TwoFeedCoordinator):

    def matches_deprecated(self):
        raise NotImplementedError()

        left_feed = self.left_feed
        right_feed = self.right_feed
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for m in right_feed.matches():
                matched = False
                for m2 in left_feed.matches():
                    diff = m.begin - m2.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(m, op=self, left=m, name=self.name)
        else:
            for m in right_feed.matches():
                for m2 in left_feed.matches():
                    diff = m.begin - m2.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(m, op=self, left=m, submatch=m2, name=self.name)
                        break

    def scan(self, start=0, end=None):
        """
        This operator is deprecated.
        """
        raise NotImplementedError()

    def __str__(self):
        return "SPrecedesFilterCoordinator(%s, %d, %d, %s, %s)" % (
            self.patname, self.proximity, self.inverted, self.left_feed, self.right_feed)


class SFollowsFilterCoordinator(TwoFeedCoordinator):

    def matches_deprecated(self):
        raise NotImplementedError()

        left_feed = self.left_feed
        right_feed = self.right_feed
        inverted = self.inverted
        proximity = self.proximity

        if inverted:
            for m in right_feed.matches():
                matched = False
                for m2 in left_feed.matches():
                    diff = m2.begin - m.end
                    if 0 <= diff <= proximity:
                        matched = True
                        break
                if not matched:
                    yield CoordMatch(m, op=self, left=m, name=self.name)
        else:
            for m in right_feed.matches():
                for m2 in left_feed.matches():
                    diff = m2.begin - m.end
                    if 0 <= diff <= proximity:
                        yield CoordMatch(m, op=self, left=m, submatch=m2, name=self.name)
                        break

    def scan(self, start=0, end=None):
        """
        This operator is deprecated.
        """
        raise NotImplementedError()

    def __str__(self):
        return "SFollowsFilterCoordinator(%s, %d, %d, %s, %s)" % (
            self.patname, self.proximity, self.inverted, self.left_feed, self.right_feed)


class JoinCoordinator(TwoFeedCoordinator):
    """
    Base class (only) for two-feed coordinators that are interested in 
    various kinds of overlaps of their two feeds.
    """

    # Generates all overlapping matches between two streams
    # TODO: Deprecate and remove once 'scan' replaces 'matches'
    def _generate_overlaps(self, include_non_overlaps=False):

        rightm = list(self.right_feed.matches())

        def overlaps(lm, rm):
            return (lm.begin <= rm.begin < lm.end or
                    lm.begin < rm.end <= lm.end or
                    rm.begin <= lm.begin < rm.end or
                    rm.begin < lm.end <= rm.end)

        for lm in self.left_feed.matches():
            for rm in (m for m in rightm if overlaps(lm, m)):
                yield lm, rm

    def _generate_overlaps_scan(self, start=0, end=None):

        rightm = list(self.right_feed.scan(start=start, end=end))

        def overlaps(lm, rm):
            return (lm.begin <= rm.begin < lm.end or
                    lm.begin < rm.end <= lm.end or
                    rm.begin <= lm.begin < rm.end or
                    rm.begin < lm.end <= rm.end)

        for lm in self.left_feed.scan(start=start, end=end):
            for rm in (m for m in rightm if overlaps(lm, m)):
                yield lm, rm

    @abstractmethod
    def scan(self, start=0, end=None):
        raise NotImplementedError()

class OverlapCoordinator(JoinCoordinator):
    """
    Matches in the left stream that overlap with some match in the right stream.
    """

    def scan(self, start=0, end=None):
        for lm, rm in self._generate_overlaps_scan(start=start, end=end):
            yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)

    def __str__(self):
        return "OverlapCoordinator(%s, %s)" % (self.left_feed, self.right_feed.__str__())


class ContainCoordinator(JoinCoordinator):
    """
    Matches in the left stream that contain some match in the right stream.
    """

    def scan(self, start=0, end=None):
        for lm, rm in self._generate_overlaps_scan(start=start, end=end):
            if lm.begin <= rm.begin and rm.end <= lm.end:
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)

    def __str__(self):
        return "ContainCoordinator(%s, %s)" % (self.left_feed, self.right_feed)



# Consider removing this operator, since there are already several ways 
# of achieving the same effect.
# contained_by(b, a)
# match(b, a)
# select(b, contains(a, b)) 
class ContainedByCoordinator(JoinCoordinator):
    """
    Matches in the left stream that are contained by some match in the right stream.
    """

    def matches_deprecated(self):
        raise NotImplementedError()

        lastm = None
        for lm, rm in self._generate_overlaps():
            if rm.begin <= lm.begin and lm.end <= rm.end:
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                # if lm is not lastm:
                #     yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                lastm = lm

    def scan(self, start=0, end=None):
        lastm = None
        for lm, rm in self._generate_overlaps_scan(start=start, end=end):
            if rm.begin <= lm.begin and lm.end <= rm.end:
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                # if lm is not lastm:
                #     yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)
                lastm = lm

    def __str__(self):
        return "ContainedByCoordinator(%s, %s)" % (self.left_feed, self.right_feed)


class IntersectionCoordinator(NFeedCoordinator):
    """
    Matches in the leftmost stream that are co-extensive in the all streams.
    """

    def scan_old(self, start=0, end=None):
        for lm, rm in self._generate_overlaps_scan(start=start, end=end):
            if lm == rm:
                # For filter-type coordinators, the new CoordMatch
                # always has the same extent as the feed match --
                # or one of them, if there are two, and currently
                # it's always the left feed match.
                yield CoordMatch(lm, op=self, left=lm, right=rm, name=self.name)

    def scan(self, start=0, end=None):
        result = None
        for feed in self.feeds:
            matches = feed.scan(start=start, end=end)
            if result is None:
                result = dict((m, CoordMatch(m, op=self, name=self.name, submatches=[m])) for m in matches)
            else:
                matched = set()
                for m in matches:
                    try:
                        result[m].submatches.append(m)
                        matched.add(m)
                    except KeyError:
                        pass
                for rm in list(result.keys()):
                    if rm not in matched:
                        del result[rm]
            if len(result) == 0:
                return
        for m in result.values():
            yield m

    def __str__(self):
        return "IntersectionCoordinator(%s)" % " , ".join(str(feed) for feed in self.feeds)


# Return all matches from the n streams.
# Any matches having the same extent produce a single match in the output.
class UnionCoordinator(NFeedCoordinator):

    def scan(self, start=0, end=None):
        result = {}
        for feed in self.feeds:
            matches = feed.scan(start=start, end=end)
            for m in matches:
                try:
                    result[m].submatches.append(m)
                except KeyError:
                    result[m] = CoordMatch(m, op=self, name=self.name, submatches=[m])
        for m in result.values():
            yield m

    def scan_old(self, start=0, end=None):
        for lm in self.left_feed.scan(start=start, end=end):
            yield CoordMatch(lm, op=self, left=lm,  submatch=lm, name=self.name)
        for rm in self.right_feed.scan(start=start, end=end):
            yield CoordMatch(rm, op=self, right=rm, submatch=rm, name=self.name)

    def __str__(self):
        return "UnionCoordinator(%s)" % " , ".join(str(feed) for feed in self.feeds)


# Return any matches in the first stream not found in any of the subsequent 
# streams (that is, matches in the first stream for which there is no match 
# in any of the subsequent streams with the same extent).
class DiffCoordinator(NFeedCoordinator):

    def scan(self, start=0, end=None):
        result = None
        for feed in self.feeds:
            matches = set(feed.scan(start=start, end=end))
            if result is None:
                result = dict((m, CoordMatch(m, op=self, name=self.name, submatch=m)) for m in matches)
            else:
                for m in list(result.keys()):
                    if m in matches:
                        del result[m]
            if len(result) == 0:
                return
        for m in result.values():
            yield m

    def scan_old(self, start=0, end=None):
        rightm = set(self.right_feed.scan(start=start, end=end))
        for lm in self.left_feed.scan(start=start, end=end):
            if lm not in rightm:
                yield CoordMatch(lm, op=self, left=lm, submatch=lm, name=self.name)

    def __str__(self):
        return "DiffCoordinator(%s)" % " , ".join(str(feed) for feed in self.feeds)


class ConnectsCoordinator(JoinCoordinator):
    """
    Produces matches based on two feeds and a parse expression extractor, 
    producing a match whenever a pair of matches from the feeds is connected 
    by the given parse tree path relationship.
    """

    # Does it make sense to use the same start/end for two different feeds? 
    # I guess what that means is that we're using the same token subsequence 
    # for interpreting _ when this connects coordinator is used as the 
    # extractor of another coordinator.
    def scan(self, start=0, end=None):
        extractor, type_ = self.parent.lookup_extractor(self.patname)
        if type_ != 'dep_fa':
            # TODO If we knew our own pattern name, we could show that here.
            raise RuntimeError("%s is not a parse pattern" % self.patname)
        leftm = list(self.left_feed.scan(start=start, end=end))
        if len(leftm) == 0:
            return
        rightm = list(self.right_feed.scan(start=start, end=end))
        if len(rightm) == 0:
            return
        for lm in leftm:
            for i in range(lm.begin, lm.end):
                # TODO? Seems like there's potential to call fam.scan here
                # as we do in most other coordinators, and thereby remove the
                # restriction that the extractor is a parse expression.
                # Interesting idea. There would be an efficiency hit, 
                # but we should explore the option.
                for pm in extractor.matches(lm.seq, i, end):
                    hits = [rm for rm in rightm if rm.covers(pm.end)]
                    for rm in hits:
                        yield CoordMatch(pm, op=self, left=lm, right=rm, submatch=pm, name=self.name)

    def requirements(self):
        return super().requirements() | self.parent.requirements(self.patname)

    def __str__(self):
        patname = self.patname
        lf = self.left_feed
        rf = self.right_feed
        return "ConnectsCoordinator(%s, %s, %s)" % (patname, lf, rf)


class HasPathFilterCoordinator(JoinCoordinator):

    # Generates all overlapping matches between two streams
    def _generate_connections(self):
        # print(self.parent)
        left = list(self.left_feed.matches())
        right = list(self.right_feed.matches())
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
            for i in range(lm.begin, lm.end):
                for j in range(rm.begin, rm.end):
                    if dpath in seq.find_paths(i, j):
                        return True
            return False

        for li in range(llen):
            for ri in range(rlen):
                # if connects(self.get_source_sequence(), li, ri, dpath):
                if connects(leftm[li].seq, li, ri, dpath):
                    yield leftm[li], rightm[ri]

    def matches_deprecated(self):
        raise NotImplementedError()

        for lm, rm in self._generate_connections():
            yield CoordMatch(lm, op=self, left=lm, right=rm, submatch=rm, name=self.name)

    def scan(self, start=0, end=None):
        """
        This operator is deprecated.
        """
        raise NotImplementedError()

    def __str__(self):
        lf = self.left_feed
        rf = self.right_feed
        dp = self.dpath
        return "HasPathFilterCoordinator(%s, %s, %s)" % (lf, rf, dp)


class WidenCoordinator(FeedCoordinator):
    """
    For coordination matches that select matches from one of their 
    input streams, this produces matches that covers the extent 
    of both (?) matches and intervening text.
    """

    def scan(self, start=0, end=None):
        feed = self.feed
        for m in feed.scan(start=start, end=end):
            yield m.widen()

    def __str__(self):
        return "WidenCoordinator(%s)" % self.feed


# Appears to have something to do with merging consecutive overlapping 
# matches within a single feed.
class MergeCoordinator(FeedCoordinator):

    def matches_deprecated(self):
        raise NotImplementedError()

        ms = sorted(list(self.feed.matches()))
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

    def scan(self, start=0, end=None):
        """
        Maybe deprecate this operator.  I don't understand its intended use.
        """
        raise NotImplementedError()

    def __str__(self):
        return "MergeCoordinator(%s)" % self.feed


# A (very modest) start on a macro capability.
class EvalCoordinator(FeedCoordinator):

    def __init__(self, **args):
        super().__init__(**args)
        self.feed = self.parent.get_coord(self.feedname)

    def scan(self, start=0, end=None):
        raise NotImplementedError()

    def __str__(self):
        return "EvalCoordinator(%s)" % self.feedname


