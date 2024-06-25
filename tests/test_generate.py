from valetrules.test.valet_test import ValetTest


# Also tests reversing a FA, which is not tested elsewhere.
# TODO? Have not tested using the "tally" statistics.
class TestGenerate(ValetTest):

    # Currently just exercises, doesn't check results, which are mostly
    # random anyway.
    def test_generate(self):
        print("test_generate")
        patterns = """
tt1 : {a b}
tt2 : {c d}
tt3 : {e f}
tt4 : {g h}
tt5 : &tt4
phrase1 -> &tt2* | &tt3*
phrase2 -> &tt1+ @phrase1+ &tt5+
        """
        self.parse_block(patterns)

        fa, _ = self.vrm.lookup_own_extractor("phrase2")
        for _ in range(10):
            state, emits = fa.generate_to()
            print(emits)

        rfa = fa.reverse()
        for _ in range(10):
            state, emits = rfa.generate_to()
            print(emits)
