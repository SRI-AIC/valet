import unittest

from valetrules.match import FAMatch, Frame
from valetrules.test.valet_test import ValetTest


class TestFrame(ValetTest):

    #  Based on the example from the documentation.
    def test_frame_1(self):
        print("test_frame_1")
        patterns="""
# stx <- syntax.vrules
name   : pos[NNP]
hire   : lemma[hire]
nsubj  ^ nsubj
dobj   ^ dobj conj*
hsubj  ~ select(hire, connects(nsubj, name, hire))
hobj   ~ select(hire, connects(dobj, hire, name))
hiring ~ union(hsubj, hobj)
hframe $ frame(hiring,
               hiring_word=hire,
               employer=hsubj name,
               employee=hobj name,
               employee2=hobj name)
        """
        self.parse_block(patterns)

        # text = "McDonald's hired Tom Smith."
        text = "McDonald's hired Tom Smith and Fred Jones."
        # "McDonald's is hiring!" or "Tom Smith got hired yesterday."
        tseq = self.tseq_from_text(text, "hframe")
 
        matches = self.matches_tseq('hframe', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("hframe", frame.name)
        self.assertEqual("hiring", frame.match.name)
        self.assertTrue('employer' in frame.fields)
        self.assertEqual("McDonald", frame.fields['employer'].matching_text())
        self.assertTrue('employee' in frame.fields)
        # Not sure the order here is guaranteed.
        # Our code does not always return matches in the expected or even 
        # deterministic order, though I keep trying to move in that 
        # direction where possible.
        employees = set([frame.fields[fname].matching_text() for fname in ['employee', 'employee2']])
        self.assertTrue("Smith" in employees)
        self.assertTrue("Jones" in employees)
        # TODO Add two more employees to the text and a third field, 
        # and show that two of the employees end up in the third field 
        # in a list.

        print("test_frame_1 done")


    # Simplified version of some rules under dev for KMASS.
    # Should probably simplify further.
    # Or maybe this is not needed anymore now that we have test_frame_1.
    def test_frame_2(self):
        print("test_frame_2")
        patterns="""
stx <- syntax.vrules
vcr ~ stx.verbal_clause_root
head_verb ~ stx.head_verb
head_noun ~ stx.head_noun
bnp ~ stx.base_noun_phrase
bvp ~ stx.base_verb_phrase

focal_noun ~ select(head_noun, bnp)
verb_with_subject ~ select(head_verb, connects(stx.subjects, focal_noun, bvp))
focal_verb ~ inter(vcr, verb_with_subject)
focal_frame $ frame(focal_verb,
                    predicate      = bvp,
                    predicate_head = bvp head_verb,
                    agent          = verb_with_subject bnp)
        """
        self.parse_block(patterns)

        text = "Bob is working on compound key resolution."
        tseq = self.tseq_from_text(text, "focal_frame")
 
        matches = self.matches_tseq('bvp', tseq)
        self.assertEqual(1, len(matches))
        matches = self.matches_tseq('focal_verb', tseq)
        self.assertEqual(1, len(matches))
        matches = self.matches_tseq('focal_frame', tseq)
        self.assertEqual(1, len(matches))

        print("test_frame_2 done")


    # Test of various forms of field RHS, exercising match query() methods.
    # TODO Currently there can be hard-to-understand interactions with imports.
    def test_frame_3(self):
        print("test_frame_3")
        # Note FWIW r-string so don't need to write \\d+ inside to avoid DeprecationWarning.
        patterns=r"""
num : /^\d+$/
whole -> @num
decimal -> @num
bignum -> &whole ( , &whole ) * ( . @decimal ) ?
currency : { $ € }

# To reproduce the issue, we need a frame to be referenced indirectly 
# in the anchor rule of another frame.
bignum_frame $ frame(bignum,
                     whole_field = whole,
                     decimal_field = decimal)

bignum_bignum ~ select(bignum, bignum_frame)
bignum_decimal ~ select(decimal, bignum_frame)
bignum_whole ~ select(whole, bignum_frame)

bignum_frame2 $ frame(bignum_bignum,
                      decimal_field_1 = bignum_frame decimal,
                      decimal_field_2 = bignum_frame decimal_field)

# I've already exercised phrase rules, let's try the prefix coordinator here instead.
# money -> &currency @bignum
# money_bignum ~ select(bignum, money)
money_bignum ~ select(bignum, prefix(currency, bignum))
currency_prefix ~ select(currency, money_bignum)
money_frame $ frame(currency_prefix,
                    currency_field = currency,
                    whole_field = whole,
                    decimal_field = decimal)
        """
        self.parse_block(patterns)

        text = "$12,345.67"
        tseq = self.tseq_from_text(text, "bignum_frame")
 
        matches = self.matches_tseq('bignum_frame', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("bignum_frame", frame.name)
        self.assertEqual("bignum", frame.match.name)
        self.assertTrue('decimal_field' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field'].matching_text())
        self.assertTrue('whole_field' in frame.fields)
        self.assertEqual(2, len(frame.fields['whole_field']))
        wholes = [f.matching_text() for f in frame.fields['whole_field']]
        self.assertTrue("12" in wholes)
        self.assertTrue("345" in wholes)

        matches = self.matches_tseq('bignum_bignum', tseq)
        self.assertEqual(1, len(matches))

        matches = self.matches_tseq('bignum_frame2', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("bignum_frame2", frame.name)
        self.assertEqual("bignum_bignum", frame.match.name)
        # I wasn't sure if this would work, but it does.
        self.assertTrue('decimal_field_2' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field_2'].matching_text())
        # TODO failing here
        # I assumed this would work, but it doesn't yet.
        # Making it do so is an enhancement not yet performed.
        # self.assertTrue('decimal_field_1' in frame.fields)
        # self.assertEqual("67", frame.fields['decimal_field_1'].matching_text())

        matches = self.matches_tseq('money_frame', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("money_frame", frame.name)
        self.assertEqual("currency_prefix", frame.match.name)
        self.assertTrue('currency_field' in frame.fields)
        self.assertEqual("$", frame.fields['currency_field'].matching_text())
        self.assertTrue('decimal_field' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field'].matching_text())
        self.assertTrue('whole_field' in frame.fields)
        self.assertEqual(2, len(frame.fields['whole_field']))
        wholes = [f.matching_text() for f in frame.fields['whole_field']]
        self.assertTrue("12" in wholes)
        self.assertTrue("345" in wholes)

        print("test_frame_3 done")


    # This is a test of the handling of import name prefixes on rule names 
    # in both explicit and implicit (frame RHS) selects.
    def test_frame_4(self):
        print("test_frame_4")
        patterns=r"""
ns1 <-
  num : /^\d+$/
  whole -> @num
  decimal -> @num
  bignum -> &whole ( , &whole ) * ( . @decimal ) ?
  bignum_whole_inner ~ select(whole, bignum)
bignum_whole_outer ~ select(whole, ns1.bignum)
bignum_frame $ frame(ns1.bignum,
                     whole_field = whole,
                     decimal_field = decimal)
        """
        self.parse_block(patterns)

        text = "$12,345.67"
        tseq = self.tseq_from_text(text, "bignum_frame")
 
        matches = self.matches_tseq('bignum_frame', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("bignum_frame", frame.name)
        self.assertEqual("ns1.bignum", frame.match.name)
        self.assertTrue('decimal_field' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field'].matching_text())
        self.assertTrue('whole_field' in frame.fields)
        self.assertEqual(2, len(frame.fields['whole_field']))
        wholes = [f.matching_text() for f in frame.fields['whole_field']]
        self.assertTrue("12" in wholes)
        self.assertTrue("345" in wholes)

        for rule in ("ns1.bignum_whole_inner",
                     "bignum_whole_outer",):
            # print(rule)
            tseq = self.tseq_from_text(text, rule)
            matches = self.matches_tseq(rule, tseq)
            # print([str(m) for m in matches])
            self.assertEqual(2, len(matches))

        print("test_frame_4 done")


    # This is a test of the handling of import name prefixes on rule names 
    # in both explicit and implicit (frame RHS) selects.
    def test_frame_5(self):
        print("test_frame_5")
        # test_frame_4 was about referencing the namespace from outside it, 
        # test_frame_5 is about referencing outside from the namespace.
        # TODO I should also check that what shouldn't work, doesn't work.
        # We don't yet a have a precise definition of that, though.
        patterns=r"""
num : /^\d+$/
whole -> @num
decimal -> @num
bignum -> &whole ( , &whole ) * ( . @decimal ) ?
bignum_whole_outer ~ select(whole, bignum)
ns1 <-
  bignum_whole_inner ~ select(whole, bignum)
  bignum_frame $ frame(bignum,
                       whole_field = whole,
                       decimal_field = decimal)
        """
        # TODO I should also try REDEFINING some things from outside 
        # in the namespace.
        self.parse_block(patterns)

        text = "$12,345.67"
        tseq = self.tseq_from_text(text, "ns1.bignum_frame")
 
        matches = self.matches_tseq('ns1.bignum_frame', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("ns1.bignum_frame", frame.name)
        self.assertEqual("bignum", frame.match.name)
        self.assertTrue('decimal_field' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field'].matching_text())
        self.assertTrue('whole_field' in frame.fields)
        self.assertEqual(2, len(frame.fields['whole_field']))
        wholes = [f.matching_text() for f in frame.fields['whole_field']]
        self.assertTrue("12" in wholes)
        self.assertTrue("345" in wholes)

        for rule in ("ns1.bignum_whole_inner",
                     "bignum_whole_outer",):
            print(rule)
            tseq = self.tseq_from_text(text, rule)
            matches = self.matches_tseq(rule, tseq)
            # print([str(m) for m in matches])
            self.assertEqual(2, len(matches))

        print("test_frame_5 done")


    # This is a test of the handling of import name prefixes on rule names 
    # in both explicit and implicit (frame RHS) selects.
    def test_frame_6(self):
        print("test_frame_6")
        patterns=r"""
ns1 <-
  num : /^\d+$/
  whole -> @num
  decimal -> @num
  bignum -> &whole ( , &whole ) * ( . @decimal ) ?
  bignum_whole_inner1 ~ select(whole, bignum)
ns2 <-
  bignum_whole_inner2 ~ select(whole, ns1.bignum)
  bignum_frame $ frame(ns1.bignum,
                       whole_field = whole,
                       decimal_field = decimal)
        """
        self.parse_block(patterns)

        text = "$12,345.67"
        tseq = self.tseq_from_text(text, "ns2.bignum_frame")
 
        matches = self.matches_tseq('ns2.bignum_frame', tseq)
        self.assertEqual(1, len(matches))
        frame = matches[0]
        self.assertTrue(isinstance(frame, Frame))
        self.assertEqual("ns2.bignum_frame", frame.name)
        self.assertEqual("ns1.bignum", frame.match.name)
        self.assertTrue('decimal_field' in frame.fields)
        self.assertEqual("67", frame.fields['decimal_field'].matching_text())
        self.assertTrue('whole_field' in frame.fields)
        self.assertEqual(2, len(frame.fields['whole_field']))
        wholes = [f.matching_text() for f in frame.fields['whole_field']]
        self.assertTrue("12" in wholes)
        self.assertTrue("345" in wholes)

        for rule in ("ns1.bignum_whole_inner1",
                     "ns2.bignum_whole_inner2",):
            print(rule)
            tseq = self.tseq_from_text(text, rule)
            matches = self.matches_tseq(rule, tseq)
            # print([str(m) for m in matches])
            self.assertEqual(2, len(matches))

        print("test_frame_6 done")



    # TODO What would be some rules that would take advantage 
    # of the way Dayne wrote the matching?
    # * He wrote it so that the match names get stripped down 
    # to the length of the query names.
    # So the match names would have to be longer. 
    # So either:
    # - we'd have to invoke the scanning with longer names 
    #   in the test code, and/or 
    # - the rules would have to use longer names 
    #   to reference other rules.
    # The second is the more important case.

    # TODO Another question would be, are there any cases 
    # where we'd want to DISALLOW what my opposite code allows?
    # Dayne wrote:
    # "It’s true that we could make that test succeed by always shortening 
    # the comparison to the shorter of qname and mname, but that seems clearly 
    # misguided to me.  For example, that would cause the following expression 
    # to succeed: “select(foo.bar.baz.whole, ns1.bignum)”.

    # This is a test of the handling of import name prefixes on rule names 
    # in both explicit and implicit (frame RHS) selects.
    # @unittest.skip("In development.")
    def test_frame_7(self):
        print("test_frame_7")
        # TODO I should also check that what SHOULDN'T work, DOESN'T work.
        # We don't yet a have a precise definition of that, though.
        patterns=r"""
ns1 <-
  num : /^\d+$/
  whole -> @num
  decimal -> @num
  bignum -> &whole ( , &whole ) * ( . @decimal ) ?
  bignum_whole_inner1 ~ select(whole, bignum)
ns2 <-
  bignum_whole_inner2 ~ select(whole, ns1.bignum)
  bignum_frame $ frame(ns1.bignum,
                       whole_field = whole,
                       decimal_field = decimal)

bignum_whole_outer2 ~ bignum_whole_inner2

# Is this a good case?
# Here presumaby the match name of the bignum rule 
# would be ns1.bignum.
# You might not want to require ns1.bignum here?
# It's probably too much bother to require the user 
# to trace through to see what match name would be 
# assigned?
# He still has to something like that for the opposite case, though.
rule ~ select(bignum, ns2.bignum_whole_inner2)

# TODO Can I come up with an analogous frame case?
        """
        self.parse_block(patterns)

        text = "$12,345.67"
        tseq = self.tseq_from_text(text, "rule")
 
        matches = self.matches_tseq('rule', tseq)
        for m in matches:
            print(m)
        # So why 2? I think it's probably because in SelectCoordinator 
        # (the one for bignum_whole_inner2) we're putting the feed match 
        # into both the "left" and "supermatch" attributes.
        # TODO I've noticed that before, and I think we should probably
        # stop doing that. 
        # Yet when I change the code locally, it's still 2?
        self.assertEqual(2, len(matches))
        # self.assertEqual(1, len(matches))

        print("test_frame_7 done")


    # Initial test, based on some unfortunately complicated rules from KMASS.
    def test_nested_frame(self):
        print("test_nested_frame")
        patterns=r"""
stx <- syntax.vrules
bnp ~ stx.base_noun_phrase
prep_word : &stx.preposition
governed_np ~ bnp
governing_np ~ bnp

prep ^ \prep
np_governed_prep ~ select(prep_word, connects(prep, governing_np, prep_word))
pobj ^ \pobj \conj*
np_governing_prep ~ select(prep_word, connects(pobj, prep_word, governed_np))
# To achieve nested frames, I need to make the inner prep_np_frame 
# selectable from the anchor rule all_np of the outer frame np_frame.
# np_np_connecting_prep ~ inter(np_governed_prep, np_governing_prep)  # original rule used with frame reduce
np_np_connecting_prep ~ inter(np_governed_prep, prep_np_frame)

prepnp_qualified_np   ~ select(governing_np, np_np_connecting_prep)
unqualified_np        ~ diff(bnp, prepnp_qualified_np)
all_np                ~ union(prepnp_qualified_np, unqualified_np)

prep_np_frame $ frame(np_governing_prep,
                      objprep=np_governing_prep,
                      prepobj=governed_np)

np_frame $ frame(all_np,
                 base=all_np,
                 prep_phrase=prep_np_frame)
#                 prep_phrase=np_np_connecting_prep)  # original RHS used with frame reduce
        """
        self.parse_block(patterns)

        text = "I want a piece of the action."
        tseq = self.tseq_from_text(text, "np_frame")

        matches = self.matches_tseq('np_frame', tseq)
        self.assertEqual(3, len(matches))
        for np_frame in matches:
            self.assertTrue(isinstance(np_frame, Frame))
            self.assertEqual("np_frame", np_frame.name)
            if np_frame.matching_text() == "a piece":
                piece_frame = np_frame
            elif np_frame.matching_text() == "the action":
                action_frame = np_frame
        self.assertEqual("a piece",    piece_frame.fields["base"].matching_text())
        self.assertEqual("of",         piece_frame.fields["prep_phrase"].fields["objprep"].matching_text())
        self.assertEqual("the action", piece_frame.fields["prep_phrase"].fields["prepobj"].matching_text())
        self.assertTrue("prep_phrase" not in action_frame.fields)
        # print(piece_frame.as_json(indent=2))
        # print(piece_frame.fields["prep_phrase"].as_json(indent=2))

        print("test_nested_frame done")


    # Simpler example based on simpler KMASS rules from Michael Wessel.
    # @unittest.skip("Not working yet.")
    def test_nested_frame_2(self):
        print("test_nested_frame_2")
        patterns=r"""
stx <- syntax.vrules
bnp ~ stx.base_noun_phrase
governed_np ~ bnp
governing_np ~ bnp

#prep_word: &stx.preposition
prep_word: {in at}i
np_prep_np1 -> @governed_np &prep_word @governing_np
np_prep_np1_frame $ frame(np_prep_np1, governed=governed_np, prep=prep_word, governing=governing_np)
# Before allowing callout from FAs to frames in the code, 
# needed to use this in synonym and syn_frame for this test to work.
# np_prep_np1_frame_coord ~ np_prep_np1_frame

# def -> are called
def -> are referred to as
left_side -> @bnp
synonym -> @left_side @def @np_prep_np1_frame

syn_frame $ frame(synonym, sub=left_side, pred=def, obj=np_prep_np1_frame)
        """
        self.parse_block(patterns)

        # I had some trouble getting this test to work with the original text. 
        # Seems related to bnp matching "called summary reports", strangely 
        # (though comprehesibly).
        # So I reworded the text and the corresponding rule ("def").
        # text = "Daily drilling reports are called summary reports at Equinor."
        text = "Daily drilling reports are referred to as summary reports at Equinor."
        tseq = self.tseq_from_text(text, "syn_frame")

        matches = self.matches_tseq('syn_frame', tseq)
        self.assertEqual(1, len(matches))
        syn_frame = matches[0]
        self.assertEqual("Daily drilling reports",
                         syn_frame.fields["sub"].matching_text())
        self.assertEqual("at",
                         syn_frame.fields["obj"].fields["prep"].matching_text())
        self.assertEqual("Equinor",
                         syn_frame.fields["obj"].fields["governing"].matching_text())
        # print(syn_frame.as_json(indent=2))
        # print(syn_frame.fields["obj"].as_json(indent=2))


        print("test_nested_frame_2 done")


if __name__ == '__main__':
    print("test_frame.py starting")
    unittest.main()
    print("test_frame.py finished")
