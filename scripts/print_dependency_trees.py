import plac

from nlpcore.annotator import Requirement
from nlpcore.tseqsrc import TokenSequenceSource


def main(target: ("File containing text to process", "positional", None, str),
         target_type: ("Type of the input: {text, directory, dirtree, ctakes, patentcsv, etc.}", "option", "y", str) = "text",
         nlp_engine: ("NLP module to use", "option", "x", str) = 'stanza',
         ):

    data_source = TokenSequenceSource.source_for_type(target_type, target, nlp_engine=nlp_engine)
    requirements = set([Requirement.POS, Requirement.DEPPARSE])
    data_source.set_requirements(requirements)

    for source, tseqs in data_source.token_sequences():
        print("SOURCE:", source.replace("\n", "\\n"))
        for tseq in tseqs:
            print("SENTENCE:", tseq.get_normalized_text().replace("\n", "\\n"))
            print("TOKENS:", tseq.tokens)
            string = tseq.dependency_tree_string()
            print(string)
        print()


plac.call(main)
