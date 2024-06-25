import sys

from nlpcore.tokenizer import PlainTextTokenizer
from valetrules.manager import VRManager

pattern_file = sys.argv[1]
pattern_name = sys.argv[2]
text = sys.argv[3]

vrm = VRManager()
vrm.parse_file(pattern_file)
tokenizer = PlainTextTokenizer(preserve_case=True, nlp_on_demand='stanza', requirements=vrm.requirements(pattern_name))

if vrm.search(pattern_name, tokenizer.tokens(text)):
    print("Text matches the pattern")
else:
    print("Text does not match the pattern")


