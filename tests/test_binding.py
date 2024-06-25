import unittest

from valetrules.test.valet_test import ValetTest


def Dont_setUpModule():  # DEBUG, disabled
    import logging.config
    from nlpcore.logging import no_datetime_config
    logging.config.dictConfig(no_datetime_config)
    logging.getLogger("valetrules.manager.<module>").setLevel("DEBUG")
    logging.getLogger("valetrules.coordinator.<module>").setLevel("DEBUG")


class TestBinding(ValetTest):

    # This tests binding IN phrase rules (and token test
    # and coord rules) but not binding OF phrase rules,
    # i.e., substituting some other phrase rule for the original one,
    # only of token tests, substituting one for another.
    def test_phrase_binding(self):
        print("test_phrase_binding")
        patterns = """
word:  /^[a-z]+$/i
cword: /^[A-Z]/
Cword: /^[A-Z]+$/

word_singleton  :             &word
# It's kind of odd to rebind your own direct reference,
# but it does work.
cword_singleton :[word=cword] &word
Cword_singleton :[word=Cword] &word

word_pair  ->             &word &word
cword_pair ->[word=cword] @word_pair
Cword_pair ->[word=Cword] @word_pair

word_pair_coord  ~             word_pair
cword_pair_coord ~[word=cword] word_pair
Cword_pair_coord ~[word=Cword] word_pair

# test re-binding; outer bindings override inner
Cword_pair_coord2 ~[word=Cword] cword_pair_coord
        """
        text = "The quick Brown Fox jumped over the LAZY DOG."

        self.parse_block(patterns)

        self.assertEqual(self.match_count('word_singleton', text), 9)
        self.assertEqual(self.match_count('cword_singleton', text), 5)
        self.assertEqual(self.match_count('Cword_singleton', text), 2)
        self.assertEqual(self.match_count('word_pair', text), 4)
        self.assertEqual(self.match_count('cword_pair', text), 2)
        self.assertEqual(self.match_count('Cword_pair', text), 1)
        self.assertEqual(self.match_count('word_pair_coord', text), 4)
        self.assertEqual(self.match_count('cword_pair_coord', text), 2)
        self.assertEqual(self.match_count('Cword_pair_coord', text), 1)
        self.assertEqual(self.match_count('Cword_pair_coord2', text), 1)

        # Verify what submatch names are in the presence of bindings
        # (at least for certain kinds of extractors).
        # Here we see that in FAs (sub)matches are recorded with the
        # actual names of the extractors used, not the formal names
        # in the rule definitions. That DOES seem like the way to go.
        matches = self.matches('Cword_pair_coord2', text)
        for match in matches:
            submatches = match.all_submatches('word')
            self.assertEqual(len(submatches), 0)
            submatches = match.all_submatches('Cword')
            self.assertEqual(len(submatches), 2)
            break  # once is enough

    # This tests binding OF phrase rules,
    # i.e., substituting some other phrase rule for the original one.
    def test_binding_of_phrase(self):
        print("test_binding_of_phrase")
        patterns = """
word:  /^[a-z]+$/i
cword: /^[A-Z]/
Cword: /^[A-Z]+$/

word_phr   -> &word
cword_phr  -> &cword
Cword_phr  -> &Cword

word_pair -> @word_phr @word_phr

cword_pair ->[word_phr=cword_phr] @word_pair
Cword_pair ->[word_phr=Cword_phr] @word_pair
        """
        text = "The quick Brown Fox jumped over the LAZY DOG."

        self.parse_block(patterns)

        self.assertEqual(self.match_count('word_pair', text), 4)
        self.assertEqual(self.match_count('cword_pair', text), 2)
        self.assertEqual(self.match_count('Cword_pair', text), 1)

    # @unittest.skip("debug")
    def test_coord_binding(self):
        print("test_coord_binding")
        patterns = """
word:  /^[a-z]+$/i
cword: /^[A-Z]/

word_pair  ->             &word &word
cword_pair ->             &cword &cword

word_pair_coord  ~             match(word_pair, _)
cword_pair_coord ~             match(cword_pair, _)

testit1 ~                       match(word_pair_coord, _)
testit2 ~[word_pair=cword_pair] match(word_pair_coord, _)

        """
        text = "The quick Brown Fox jumped over the LAZY DOG."

        self.parse_block(patterns)

        # self.assertEqual(self.match_count('word_pair_coord', text), 4)
        # self.assertEqual(self.match_count('cword_pair_coord', text), 2)
        # self.assertEqual(self.match_count('Cword_pair_coord', text), 1)
        # These are the key tests here.
        self.assertEqual(self.match_count('testit1', text), 4)
        self.assertEqual(self.match_count('testit2', text), 2)

    def test_reference_tokentest(self):
        print("test_reference_tokentest")
        patterns = """
word:  /^[a-z]+$/i
cword: /^[A-Z]/
Cword: /^[A-Z]+$/

word_singleton  :             &word
cword_singleton :[word=cword] &word
Cword_singleton :[word=Cword] &word

# Single reference.
word_ref  : &word
# Reference to reference (double reference).
word_ref2 : &word_singleton
cword_ref2 : &cword_singleton
Cword_ref2 : &Cword_singleton
        """
        text = "The quick Brown Fox jumped over the LAZY DOG."

        self.parse_block(patterns)

        self.assertEqual(self.match_count('word_ref', text), 9)
        self.assertEqual(self.match_count('word_ref2', text), 9)
        self.assertEqual(self.match_count('cword_ref2', text), 5)
        self.assertEqual(self.match_count('Cword_ref2', text), 2)


if __name__ == '__main__':
    print("test_binding.py starting")
    unittest.main()
    print("test_binding.py finished")
