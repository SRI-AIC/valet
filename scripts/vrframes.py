#!/usr/bin/env python

import re
from importlib import import_module
import plac
from valetrules.manager import VRManager
from nlpcore.tseqsrc import TokenSequenceSource


def main(pattern_file: ("File containing VR definitions", "positional", None, str),
         target: ("File containing text to process", "positional", None, str),
         patterns: ("Names of the pattern to apply (space delimited)", "positional", None, str),
         target_type: ("Type of the input: {text, directory, ctakes, patentcsv}", "option", "y", str) = "text",
         added_import: ("Additional import", "option", "i", str) = None):

    if added_import is not None:
        import_module(added_import)

    data_source = TokenSequenceSource.source_for_type(target_type, target, False)

    vrm = VRManager()
    vrm.parse_file(pattern_file)

    pattern_names = re.findall(r'\S+', patterns)

    # Inform data source about the needed NLP requirements
    requirements = set()
    for name in pattern_names:
        requirements |= vrm.requirements(name)
    data_source.add_requirements(requirements)

    for source, tseqs in data_source.token_sequences():
        print("SOURCE:", source)
        for tseq in tseqs:
            print("SENTENCE:", tseq.get_normalized_text())
            for pattern in pattern_names:
                extractor, type_ = vrm.lookup_extractor(pattern)
                if type_ != 'frame':
                    continue
                extractor.set_source_sequence(tseq)
                for frame in extractor.extract():
                    print(frame.as_json())
        print()


plac.call(main)




