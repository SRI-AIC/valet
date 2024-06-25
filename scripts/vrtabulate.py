from datetime import datetime
import re
import sys

import plac

from valetrules.manager import VRManager
from nlpcore.tseqsrc import TokenSequenceSource
from nlpcore.term_expansion import TermExpansion


def tabulate(source, vrm, pattern_name, max_sequences=None, headword_only=0):
    result = {}
    tseqs = []
    for file, ts in source.token_sequences():
        tseqs.append(ts)
    total = sum(len(ts) for ts in tseqs)
    count = 0
    for ts in tseqs:
        vrm.clear_recorded()
        for tseq in ts:
            for m in vrm.scan(pattern_name, tseq):
                if headword_only:
                    key = tseq[m.end-1]
                else:
                    key = ' '.join([tseq[i] for i in range(m.begin, m.end)])
                try:
                    result[key] += 1
                except KeyError:
                    result[key] = 1
            count += 1
            if count % 100 == 0:
                print("\r%d/%d" % (count, total), file=sys.stderr, end='')
            if max_sequences is not None and count >= max_sequences:
                break
    print("\n", file=sys.stderr)
    return result


if __name__ == "__main__":

    from nlpcore.projectsrc import PROJECT_SOURCES
    for label, src in PROJECT_SOURCES.items():
        TokenSequenceSource.add_token_sequence_source(label, src)
    source_types = TokenSequenceSource.available_type_labels()

    def main(pattern_file: ("File containing definitions", "positional"),
             source_file: ("Name of the text source", "positional"),
             pattern_name: ("Name of pattern to apply", "positional"),
             target_type: ("Type of the input", "option", "y", str) = "text",
             nlp_engine: ("NLP module to use", "option", "x", str) = 'stanza',
             headword_only: ("If true, tabulate only the final word", "option", "w", int) = 0,
             max_sequences: ("Maximum number of sequences to process", "option", "m", int) = None,
             embedding_file: ("Path to a file containing word embeddings", "option", "b", str) = None,
             term_expansion: ("Path to term expansion data; if available", "option", "t", str) = None,
             source_arguments: ("Extra args to provide to the token sequence source", "option", "g", str) = None):

        if nlp_engine == 'off':
            nlp_engine = None
        aux_args = {}
        if source_arguments is not None:
            for m in re.finditer(r'(\w+)=(\S+)', source_arguments):
                aux_args[m.group(1)] = m.group(2)

        data_source = TokenSequenceSource.source_for_type(target_type, source_file, nlp_engine=nlp_engine, **aux_args)

        if embedding_file is None:
            embedding = None
        else:
            from valetrules.extml import Embedding
            embedding = Embedding(embedding_file)

        vrm = VRManager(embedding=embedding)

        if term_expansion is not None:
            time = datetime.now().strftime("%H:%M:%S")
            print(f"{time}: Loading term expansion data...")
            expander = TermExpansion(input_directory=term_expansion)
            expander.read_term_expansion_data()
            time = datetime.now().strftime("%H:%M:%S")
            print(f"{time}: ...Done!")
            vrm.set_expander(expander)

        vrm.parse_file(pattern_file)
        requirements = vrm.requirements(pattern_name)
        data_source.set_requirements(requirements)

        histogram = tabulate(data_source, vrm, pattern_name, max_sequences=max_sequences, headword_only=headword_only)
        for key in sorted(histogram, key=lambda x: histogram[x], reverse=True):
            print(histogram[key], key)

    plac.call(main)
