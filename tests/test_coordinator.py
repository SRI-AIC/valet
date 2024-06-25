import unittest

from valetrules.test.valet_test import ValetTest

from tests.text import TEST_TEXT, TEXTS


class TestCoordinator(ValetTest):

    def test_match_within_match(self):
        print("test_match_within_match")
        patterns = """
adj : pos[JJ]
# Had to add NNP here due to bad Spacy POS-ing in 3.4.0 and 3.4.1.
noun : pos[NN NNS NNP]
noun_phrase -> &adj+ &noun
noun_in_phrase ~ match(noun, noun_phrase)
noun_coord ~ match(noun, _)
#noun_phrase_coord ~ match(noun_phrase, _)
noun_in_phrase2 ~ match(noun_coord, noun_phrase)
        """
        text = "Long pants and short sleeve shirt."
        self.parse_block(patterns)
        for rule, count in [
                ('noun_phrase', 2),
                ('noun_in_phrase', 2),
                # Test with outer match being a coordinator, not just a phrase expr.
                ('noun_in_phrase2', 2)]:
            with self.subTest(rule=rule, count=count):
                self.assertEqual(self.match_count(rule, text), count)
        print("test_match_within_match done")


    # The example noted below seemed unintuitive when Bob encountered it,
    # but our established semantics is that "*any* named extractor implicated
    # in the production of a match stream is available to 'select'".
    # There are some exceptions to that semantics, but that's a separate issue.
    # We will stick with the behavior on this example.
    def test_select_2(self):
        print("test_select_2")
        patterns = """
adj : pos[JJ]
# Had to add NNP here due to bad Spacy POS-ing in 3.4.0 and 3.4.1.
noun : pos[NN NNS NNP]
noun_phrase -> &adj+ &noun
noun_in_phrase ~ select(noun, noun_phrase)
bad ~ select(adj, noun_in_phrase)
        """
        text = "Long pants and short sleeve shirt."
        self.parse_block(patterns)
        self.assertEqual(self.match_count('noun_phrase', text), 2)
        self.assertEqual(self.match_count('noun_in_phrase', text), 2)
        # It seemed unintuitive to select an adjective from a noun,
        # but with appropriate documentation it becomes intuitive.
        # It's primarily a matter of the supermatch field being
        # among those returned from all_matches, but for select
        # the same supermatch is also stored as the "left" submatch.
        self.assertEqual(self.match_count('bad', text), 2)
        print("test_select_2 done")


    def test_select(self):
        print("test_select")
        patterns = """
any : /./
tokens : { tokens }
phrase1 -> &any
phrase2 -> &any+
phrase3 -> &any &tokens
parse ^ amod

# Matches vs _.
match00 ~ match(any, _)
match0 ~ match(tokens, _)
match1 ~ match(phrase1, _)
match2 ~ match(phrase2, _)
match3 ~ match(phrase3, _)

# Selects vs _. Should return no matches.
select000 ~ select(any, _)
select00 ~ select(tokens, _)
select01 ~ select(phrase1, _)

# Selects vs phrase1.
select100 ~ select(any, phrase1)
select10 ~ select(tokens, phrase1)
select11 ~ select(phrase1, phrase1)

# Selects vs phrase3.
select300 ~ select(any, phrase3)
select30 ~ select(tokens, phrase3)
select31 ~ select(phrase3, phrase3)

#select5 ~ select(any, match)
#select6 ~ select(tokens, match)
        """
        """
filter ~
union ~
connects ~
        """
        text = "Long tokens are not a problem."
        self.parse_block(patterns)

        # First establish matching behavior at the vrm.scan level in match_count.
        with self.subTest(rule='any', count=7):
            self.assertEqual(self.match_count('any', text), 7)
        self.assertEqual(self.match_count('any', text), 7)
        self.assertEqual(self.match_count('tokens', text), 1)
        self.assertEqual(self.match_count('phrase1', text), 7)
        self.assertEqual(self.match_count('phrase2', text), 1)
        self.assertEqual(self.match_count('phrase3', text), 1)

        # Now check the matching behavior via the match coordinator.
        # Should return basically the same matches as above, except that they
        # will be CoordMatches rather than FAMatches (note some of the
        # FAMatches are really token test expr matches, not phrase expr
        # matches), and they will hold references to those FAMatches.
        self.assertEqual(self.match_count('match00', text), 7)
        self.assertEqual(self.match_count('match0', text), 1)
        self.assertEqual(self.match_count('match1', text), 7)
        self.assertEqual(self.match_count('match2', text), 1)
        self.assertEqual(self.match_count('match3', text), 1)

        # Now check the selecting behavior via the select coordinator.

        # _ has no submatches to be selected.
        self.assertEqual(self.match_count('select000', text), 0)
        self.assertEqual(self.match_count('select00', text), 0)
        self.assertEqual(self.match_count('select01', text), 0)

        # tokens is not part of phrase1.
        # select11 ~ select(phrase1, phrase1) means
        # select11 ~ select(phrase1, match(phrase1, _))
        # and each CoordMatch from that match operation will contain one
        # FAMatch of phrase1 as a submatch, and each of those CoordMatches
        # will be a submatch of the CoordMatches for select11.
        self.assertEqual(self.match_count('select100', text), 7)
        self.assertEqual(self.match_count('select10', text), 0)
        self.assertEqual(self.match_count('select11', text), 7)

        self.assertEqual(self.match_count('select300', text), 1)
        self.assertEqual(self.match_count('select30', text), 1)
        self.assertEqual(self.match_count('select31', text), 1)

        # self.assertEqual(self.match_count('select2', text), 1)
        # self.assertEqual(self.match_count('select3', text), 7)
        # self.assertEqual(self.match_count('select4', text), 1)

        print("test_select done")


    def test_filter(self):
        print("test_filter")
        patterns = """
runner -> runner
runner_coord ~ match(runner, _)
text_with_runner ~ filter(runner, _)
text_without_runner ~ filter(runner, _, invert)
text_with_runner_coord ~ filter(runner_coord, _)
text_without_runner_coord ~ filter(runner_coord, _, invert)
        """
        self.parse_block(patterns)
        for rule, texti, count in [
                ('text_with_runner', 0, 1),
                ('text_with_runner', 1, 1),
                ('text_with_runner', 2, 0),
                ('text_with_runner', 3, 0),
                ('text_without_runner', 0, 0),
                ('text_without_runner', 1, 0),
                ('text_without_runner', 2, 1),
                ('text_without_runner', 3, 1),
                ('text_with_runner_coord', 0, 1),
                ('text_with_runner_coord', 1, 1),
                ('text_with_runner_coord', 2, 0),
                ('text_with_runner_coord', 3, 0),
                ('text_without_runner_coord', 0, 0),
                ('text_without_runner_coord', 1, 0),
                ('text_without_runner_coord', 2, 1),
                ('text_without_runner_coord', 3, 1)]:
            with self.subTest(rule=rule, texti=texti, count=count):
                self.assertEqual(self.match_count(rule, TEXTS[texti]), count)
        print("test_filter done")


    def test_proximity(self):
        print("test_proximity")
        patterns = """
lparen : { ( }
rparen : { ) }
assert : /^assert.*/i
assertnear ~ near(assert, 2, rparen)
assertprecedes ~ precedes(assert, 2, rparen)
assertfollows ~ follows(rparen, 2, assert)
        """
        self.parse_block(patterns)
        self.assertEqual(self.match_count('assertnear', TEST_TEXT), 5)
        self.assertEqual(self.match_count('assertprecedes', TEST_TEXT), 4)
        self.assertEqual(self.match_count('assertfollows', TEST_TEXT), 4)
        print("test_proximity done")

    # Here I'm double-checking something I said in the Valet Zoom channel
    # in the thread of 3/30/2022 9:27AM.
    # More generally, this test verifies that the prefix and suffix operatprs
    # are equivalent to the precedes and follows operators, respectively,
    # with proximity 0.
    def test_proximity_2(self):
        print("test_proximity_2")
        patterns = """
statement -> @left = @right
left : { a }
right : { b }
rule ~ select(left, statement)
equals : { = }
# Read as: "equals is a suffix of left"
rule2 ~ select(left, suffix(equals, left))
# "equals follows left at proximity 0"
rule3 ~ select(left, follows(equals, 0, left))
rule4 ~ select(right, prefix(equals, right))
rule5 ~ select(right, precedes(equals, 0, right))
rule6 ~ suffix(equals, left)
rule7 ~ follows(equals, 0, left)
rule8 ~ prefix(equals, right)
rule9 ~ precedes(equals, 0, right)
        """
        self.parse_block(patterns)
        text = "a = b"
        self.assertEqual(self.match_count('rule', text), 1)
        self.assertEqual(self.match_count('rule2', text), 1)
        self.assertEqual(self.match_count('rule3', text), 1)
        self.assertEqual(self.match_count('rule4', text), 1)
        self.assertEqual(self.match_count('rule5', text), 1)
        self.assertEqual(self.match_count('rule6', text), 1)
        self.assertEqual(self.match_count('rule7', text), 1)
        self.assertEqual(self.match_count('rule8', text), 1)
        self.assertEqual(self.match_count('rule9', text), 1)
        print("test_proximity_docs done")


    # This has to do with testing passing around end args to VRManager
    # and coordinators.
    def test_something(self):
        print("test_something")
        patterns = """
lparen : { ( }
rparen : { ) }
dollar : { $ }
number : /[0-9]+/
not_rparen : not &rparen
any_in_parens -> &lparen &not_rparen+ &rparen
money1 ~ prefix(dollar, number)
money2 ~ suffix(number, dollar)
test1 ~ filter(money1, any_in_parens)
test2 ~ filter(money2, any_in_parens)
test3 ~ prefix(money1, any_in_parens)
        """
        self.parse_block(patterns)
        text = "[abc] ($26) [$27] (abc)"
        self.assertEqual(self.match_count('test1', text), 1)
        self.assertEqual(self.match_count('test2', text), 1)
        text = "hello $26 (whatever) goodbye"
        self.assertEqual(self.match_count('test3', text), 1)
        print("test_something done")


    def test_count(self):
        print("test_count")
        patterns = """
assert : /^assert.*/i
two_plus_asserts ~ count(assert, 2, _)
not_two_plus_asserts ~ count(assert, 2, _, invert)
        """
        self.parse_block(patterns)
        text0 = "I am great."
        text1 = "I assert that I am great."
        text2 = "I assert that I asserted that I am great."
        text3 = "I am asserting that I have asserted that I assert that I am great."
        self.assertEqual(self.match_count('two_plus_asserts', text0), 0)
        self.assertEqual(self.match_count('two_plus_asserts', text1), 0)
        self.assertEqual(self.match_count('two_plus_asserts', text2), 1)
        self.assertEqual(self.match_count('two_plus_asserts', text3), 1)
        self.assertEqual(self.match_count('not_two_plus_asserts', text0), 1)
        self.assertEqual(self.match_count('not_two_plus_asserts', text1), 1)
        self.assertEqual(self.match_count('not_two_plus_asserts', text2), 0)
        self.assertEqual(self.match_count('not_two_plus_asserts', text3), 0)
        print("test_count done")


    # There is now a distiction between join and nfeed coordinators, FWIW;
    # inter is now nfeed.
    def test_join(self):
        print("test_join")
        patterns = """
adj : pos[JJ]
# Had to add NNP here due to bad Spacy POS-ing in 3.4.0 and 3.4.1.
noun : pos[NN NNS NNP]
noun_phrase -> &adj+ &noun
noun_in_phrase ~ select(noun, noun_phrase)
inter1 ~ inter(noun, noun_in_phrase)
inter2 ~ inter(noun_in_phrase, noun)
inter3 ~ inter(noun, noun)
inter4 ~ inter(noun_in_phrase, noun_in_phrase)
inter5 ~ inter(noun, noun_phrase)
inter6 ~ inter(noun_phrase, noun)
overlaps1 ~ overlaps(noun, noun_in_phrase)
overlaps2 ~ overlaps(noun_in_phrase, noun)
overlaps3 ~ overlaps(noun, noun)
overlaps4 ~ overlaps(noun_in_phrase, noun_in_phrase)
overlaps5 ~ overlaps(noun, noun_phrase)
overlaps6 ~ overlaps(noun_phrase, noun)
contains1 ~ contains(noun, noun_in_phrase)
contains2 ~ contains(noun_in_phrase, noun)
contains3 ~ contains(noun, noun)
contains4 ~ contains(noun_in_phrase, noun_in_phrase)
contains5 ~ contains(noun, noun_phrase)
contains6 ~ contains(noun_phrase, noun)
contained_by1 ~ contained_by(noun, noun_in_phrase)
contained_by2 ~ contained_by(noun_in_phrase, noun)
contained_by3 ~ contained_by(noun, noun)
contained_by4 ~ contained_by(noun_in_phrase, noun_in_phrase)
contained_by5 ~ contained_by(noun, noun_phrase)
contained_by6 ~ contained_by(noun_phrase, noun)
        """
        text = "Long pants and short sleeve shirt."
        self.parse_block(patterns)
        self.assertEqual(self.match_count('inter1', text), 2)  # pants sleeve
        self.assertEqual(self.match_count('inter2', text), 2)
        self.assertEqual(self.match_count('inter3', text), 3)  # also shirt
        self.assertEqual(self.match_count('inter4', text), 2)
        self.assertEqual(self.match_count('inter5', text), 0)
        self.assertEqual(self.match_count('inter6', text), 0)
        self.assertEqual(self.match_count('overlaps1', text), 2)
        self.assertEqual(self.match_count('overlaps2', text), 2)
        self.assertEqual(self.match_count('overlaps3', text), 3)
        self.assertEqual(self.match_count('overlaps4', text), 2)
        self.assertEqual(self.match_count('overlaps5', text), 2)
        self.assertEqual(self.match_count('overlaps6', text), 2)
        self.assertEqual(self.match_count('contains1', text), 2)
        self.assertEqual(self.match_count('contains2', text), 2)
        self.assertEqual(self.match_count('contains3', text), 3)
        self.assertEqual(self.match_count('contains4', text), 2)
        self.assertEqual(self.match_count('contains5', text), 0)
        self.assertEqual(self.match_count('contains6', text), 2)
        self.assertEqual(self.match_count('contained_by1', text), 2)
        self.assertEqual(self.match_count('contained_by2', text), 2)
        self.assertEqual(self.match_count('contained_by3', text), 3)
        self.assertEqual(self.match_count('contained_by4', text), 2)
        self.assertEqual(self.match_count('contained_by5', text), 2)
        self.assertEqual(self.match_count('contained_by6', text), 0)
        print("test_join done")

    # See comments at SequenceStartFiniteAutomaton concerning two possible
    # semantics for the START/END extractors. We are using the first of those.
    def test_start_end(self):
        print("test_start_end")
        patterns = r"""
num : /^\d+$/
all_numbers -> @START &num+ @END
number_runs -> &num+
#test1 ~ filter(all_numbers, 0, number_runs)
test1 ~ filter(all_numbers, number_runs)
test2 ~ match(all_numbers, number_runs)
        """
        self.parse_block(patterns)
        # If the bounds of the number_runs matches are respected,
        # all matches of number_runs should match all_numbers
        # and be passed by the filter, but if the match bounds are
        # not respected, none from text2 will be passed.
        # We are choosing to NOT respect those match bounds,
        # only the start and end of the full token sequence.
        text1 = "1 23 456 7890"
        text2 = "1 23 surprise 456 7890"
        self.assertEqual(self.match_count('number_runs', text1), 1)
        self.assertEqual(self.match_count('test1', text1), 1)
        self.assertEqual(self.match_count('number_runs', text2), 2)
        # This is the first semantics behavior.
        self.assertEqual(self.match_count('test1', text2), 0)
        self.assertEqual(self.match_count('test2', text2), 0)
        # This would be the second semantics behavior.
        # self.assertEqual(self.match_count('test1', text2), 1)
        # self.assertEqual(self.match_count('test2', text2), 2)
        print("test_start_end done")


    # See CoordMatch.normalize_endpoints().
    def test_normalize_endpoints(self):
        print("test_normalize_endpoints")
        patterns = r"""
bi   ^ nsubj
up   ^ /nsubj
down ^ \nsubj
c1a  ~ union(up)
c1b  ~ union(up, up)
c2a  ~ union(down)
c2b  ~ union(down, down)
c3   ~ union(up, down)
c4   ~ union(down, up)
        """
        self.parse_block(patterns)

        def all_reversed(matches):
            return all(m.begin > m.end for m in matches)
        def none_reversed(matches):
            return all(m.end > m.begin for m in matches)

        text = "Rita bought an apple"
        tseq, matches = self.tseq_and_matches('c1a', text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 1)
        self.assertTrue(none_reversed(matches[0].submatches))
        self.assertTrue(none_reversed(matches))

        tseq, matches = self.tseq_and_matches('c1b', text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 2)
        self.assertTrue(none_reversed(matches[0].submatches))
        self.assertTrue(none_reversed(matches))

        tseq, matches = self.tseq_and_matches('c2a', text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 1)
        self.assertTrue(all_reversed(matches[0].submatches))
        self.assertTrue(all_reversed(matches))

        tseq, matches = self.tseq_and_matches('c2b', text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 2)
        self.assertTrue(all_reversed(matches[0].submatches))
        self.assertTrue(all_reversed(matches))

        tseq, matches = self.tseq_and_matches('c3',  text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 2)
        self.assertFalse(all_reversed(matches[0].submatches))
        self.assertFalse(none_reversed(matches[0].submatches))
        self.assertTrue(none_reversed(matches))

        tseq, matches = self.tseq_and_matches('c4',  text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].submatches), 2)
        self.assertFalse(all_reversed(matches[0].submatches))
        self.assertFalse(none_reversed(matches[0].submatches))
        self.assertTrue(none_reversed(matches))
        print("test_normalize_endpoints done")


    def test_when(self):
        print("test_when")

        patterns = """
overly_general_pattern -> &ANY &ANY
symptom_header -> SYMPTOMS
medications_header -> MEDICATIONS
symptom ~ when(symptom_header and not medications_header,
               overly_general_pattern)
        """
        self.parse_block(patterns)

        patname = "symptom"
        text1 = "Stuff 1."
        text2 = "SYMPTOMS."
        text3 = "The agony of defeat."
        text4 = "MEDICATIONS."
        text5 = "Stuff 3."
        for text, count in [
                (text1, 0),
                (text2, 0),
                (text3, 2),
                (text4, 1),
                (text5, 0),]:
            with self.subTest(text=text, count=count):
                self.assertEqual(self.match_count(patname, text), count)
        print("test_when done")

    # Dotted names, but not substitutions.
    def test_when_2(self):
        print("test_when_2")

        patterns = """
nsp <-
  overly_general_pattern -> &ANY &ANY
  symptom_header -> SYMPTOMS
medications_header -> MEDICATIONS
symptom ~ when(nsp.symptom_header and not medications_header,
               nsp.overly_general_pattern)
        """
        self.parse_block(patterns)

        patname = "symptom"
        text1 = "Stuff 1."
        text2 = "SYMPTOMS."
        text3 = "The agony of defeat."
        text4 = "MEDICATIONS."
        text5 = "Stuff 3."
        for text, count in [
                (text1, 0),
                (text2, 0),
                (text3, 2),
                (text4, 1),
                (text5, 0),]:
            with self.subTest(text=text, count=count):
                matches = self.matches(patname, text)
                self.assertEqual(len(matches), count)
        print("test_when_2 done")

    # Small change from test_when_2. (Add @any rule.)
    # Wrote for debugging, keep for now.
    @unittest.skip("debug")
    def test_when_3(self):
        print("test_when_3")

        patterns = """
nsp <-
  any -> &ANY
  overly_general_pattern -> @any @any
  symptom_header -> SYMPTOMS
medications_header -> MEDICATIONS
symptom ~ when(nsp.symptom_header and not medications_header,
               nsp.overly_general_pattern)
        """
        self.parse_block(patterns)

        patname = "symptom"
        text1 = "Stuff 1."
        text2 = "SYMPTOMS."
        text3 = "The agony of defeat."
        text4 = "MEDICATIONS."
        text5 = "Stuff 3."
        for text, count in [
                (text1, 0),
                (text2, 0),
                (text3, 2),
                (text4, 1),
                (text5, 0),]:
            with self.subTest(text=text, count=count):
                matches = self.matches(patname, text)
                self.assertEqual(len(matches), count)
        print("test_when_3 done")

    # Dayne cited a situation sort of like this one.
    def test_when_4(self):
        print("test_when_4")

        patterns = """
stx <- syntax.vrules
overly_general_pattern : &stx.noun and not { MEDICATIONS FAMILY HISTORY }
medications_header -> MEDICATIONS
family_history_header -> FAMILY HISTORY
medication ~ when(medications_header and not family_history_header,
               overly_general_pattern)
        """
        self.parse_block(patterns)

        patname = "medication"
        text1 = "Stuff 1."
        text2 = "MEDICATIONS aspirin."
        text3 = "FAMILY HISTORY no problems."
        text4 = "Stuff 3."
        for text, count in [
                (text1, 0),
                (text2, 0),
                (text3, 1),  # "problems"
                (text4, 0),]:
            with self.subTest(text=text, count=count):
                matches = self.matches(patname, text)
                # print(text, [str(m) for m in matches])
                self.assertEqual(len(matches), count)
        print("test_when_4 done")


if __name__ == '__main__':
    print("test_coordinator.py starting")
    unittest.main()
    print("test_coordinator.py finished")
