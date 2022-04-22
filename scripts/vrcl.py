#!/usr/bin/env python

import re
import plac
from valetrules.manager import VRManager
from nlpcore.tseqsrc import TokenSequenceSource


def main(pattern_file: ("File containing VR definitions", "positional", None, str),
         target: ("File containing text to process", "positional", None, str),
         pattern_names: ("Names of the pattern to apply", "positional", None, str),
         markup: ("Action: Show markup", "flag", "m"),
         extract: ("Action: List extractions", "flag", "e"),
         deppaths: ("Action: Show dependency paths", "flag", "d"),
         grep: ("Action: Scan for matching records", "flag", "g"),
         conll: ("Action: Produce CoNLL-style output", "flag", "c"),
         trim: ("Option: Only show matching lines with mark up", "flag", "t"),
         nlp_engine: ("Option: Select specific NLP engine to use", "option", "x") = 'stanza',
         source_type: ("Option: Type of the input: {text, directory, ...}", "option", "y", str) = "text",
         project_source_type: ("Option: Name of project-specific source", "option", "p", str) = None,
         source_arguments: ("Option: Extra args to provide to the token sequence source", "option", "a", str) = None,  # usually -g, but that's taken above
         ):

    if not (markup or extract or deppaths or conll or grep):
        print("No useful action specified")
        exit()

    if nlp_engine == 'off':
        nlp_engine = None

    aux_args = {}
    if source_arguments is not None:
        for m in re.finditer(r'(\w+)=(\S+)', source_arguments):
            aux_args[m.group(1)] = m.group(2)

    if project_source_type is None:
        data_source = TokenSequenceSource.source_for_type(source_type, target, nlp_engine=nlp_engine, **aux_args)
    else:
        from nlpcore import projectsrc
        data_source = projectsrc.PROJECT_SOURCES[project_source_type](target, nlp_engine=nlp_engine, **aux_args)

    vrm = VRManager()
    vrm.parse_file(pattern_file)

    pattern_names = re.split(r'\s+', pattern_names)
    pattern_name = pattern_names[0]

    # Inform data source about the needed NLP requirements
    requirements = set()
    for name in pattern_names:
        requirements |= vrm.requirements(name)
    data_source.add_requirements(requirements)

    for source, tseqs in data_source.token_sequences():
        if grep:
            for tseq in tseqs:
                if vrm.search(pattern_name, tseq):
                    print(source)
                    break
        if markup:
            print("SOURCE:", source)
            data_markup = vrm.markup_from_token_sequences(pattern_name, tseqs, trim=trim != 0)
            print(data_markup)
            print()
        if extract:
            print("SOURCE:", source)
            extractions = vrm.extract_from_token_sequences(pattern_name, tseqs)
            print(extractions)
            print()
        if deppaths:
            print("SOURCE:", source)
            paths = vrm.dpaths_from_token_sequences(pattern_name, tseqs)
            for path, text in paths:
                print(path, text)
            print()
        if conll:
            output = vrm.conll_from_token_sequences(pattern_names, tseqs)
            print(output)


plac.call(main)
