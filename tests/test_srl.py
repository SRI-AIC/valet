import datetime
import unittest

from nlpcore.annotator import Requirement
from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager
from valetrules.match import FAMatch, FAArcMatch, CoordMatch
from valetrules.test.valet_test import ValetTest


class TestSRL(ValetTest):

    # Override superclass to specify allensrl.
    def setUp(self):
        self.tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand="allensrl")
        self.vrm = VRManager()

    def tseq_from_text(self, text, rulename=None):  # override superclass
        if rulename is not None:
            reqs = self.vrm.requirements(rulename)
            # TODO? Quick hack, investigate further later.
            # https://github.com/huggingface/neuralcoref/issues/117
            reqs.add(Requirement.DEPPARSE)
            self.tokenizer.set_requirements(reqs)
        return self.tokenizer.tokens(text)

    def matches_tseq(self, rulename, tseq):  # override superclass
        print(", ".join(f"{i}={tok}" for i, tok in enumerate(tseq.tokens)))
        matches = self.vrm.scan(rulename, tseq)
        matches = list(matches)
        # Have to do this after the scan (and list).
        # print(tseq.dependency_tree_string())
        # print(rulename, [str(m) for m in matches])
        return matches


    text1 = 'For example, with NAI=<5G-GUTI>@nai.5gc-nn.mnc123.mcc45.3gppnetwork.org, the N5CW device indicates that it wants "5G connectivity-without-NAS" (5gc-nn) to the PLMN with MCC=45 and MNC=123.'
    # Version without such a long match, to reduce the N in O(N^2).
    text2 = 'For example, with NAI=<5G-GUTI>@nai.org, the N5CW device indicates that it wants "5G connectivity-without-NAS" (5gc-nn) to the PLMN with MCC=45 and MNC=123.'
    texts1 = ['For example, with NAI=<5G-GUTI>@nai.org, the N5CW device indicates that it wants "5G connectivity".',
              'For example, with NAI=<5G-GUTI>@nai.3gppnetwork.org, the N5CW device indicates that it wants "5G connectivity".',
              'For example, with NAI=<5G-GUTI>@nai.mcc45.3gppnetwork.org, the N5CW device indicates that it wants "5G connectivity".',
              'For example, with NAI=<5G-GUTI>@nai.mnc123.mcc45.3gppnetwork.org, the N5CW device indicates that it wants "5G connectivity".',
              'For example, with NAI=<5G-GUTI>@nai.5gc-nn.mnc123.mcc45.3gppnetwork.org, the N5CW device indicates that it wants "5G connectivity".',
              ]


    # John N wrote:
    # "I don't know if it's this sentence on its own, or the interaction between it
    # and my rules, but something is causing Valet match to recurse in a bad way."
    # I (Bob) now think the main problem is with the name_final rule's resemblance 
    # to the example here: https://www.rexegg.com/regex-explosive-quantifiers.html
    @unittest.skip("debug")
    def test_srl_anomaly_1(self):
        print("test_srl_anomaly_1")
        patterns = """
ops5g_rules <- /Users/sasseen/Downloads/ops5g.vrules
        """
        self.parse_block(patterns)

        # for frame_rule in ['procedure_step']:
        #     print(f"## {frame_rule}")
        #     matches = self.matches(f'ops5g_rules.{frame_rule}', text)
        #     print([str(match) for match in matches])

        rule = 'name_final'
        print(f"## {rule}")
        for i, text in enumerate(self.texts1):
            print(i)
            print(datetime.datetime.now())
            matches = self.matches(f'ops5g_rules.{rule}', text)
            print(datetime.datetime.now())
            # print([str(match) for match in matches])
        print("test_srl_anomaly_1 done")

    def dont_test_srl_anomaly_2(self):
        print("test_srl_anomaly_2")
        patterns = """
ops5g_rules <- /Users/sasseen/Downloads/ops5g.vrules
        """
        self.parse_block(patterns)

        # for frame_rule in ['procedure_step']:
        #     print(f"## {frame_rule}")
        #     matches = self.matches(f'ops5g_rules.{frame_rule}', text)
        #     print([str(match) for match in matches])

        rule = 'name_final'
        print(f"## {rule}")
        for i, text in enumerate(self.texts):
            print(i)
            print(datetime.datetime.now())
            matches = self.matches(f'ops5g_rules.{rule}', self.text2)
            print(datetime.datetime.now())
            # print([str(match) for match in matches])
        print("test_srl_anomaly_2 done")
