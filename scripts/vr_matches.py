#!/usr/bin/env python

"""
For each pattern name given, writes a file with the extracted strings; 
filename is pattern name plus ".txt" extension.
One string is written per line; newline characters are replaced with "\n".
There are options for deduplication and sorting.

Also writes to stdout the names of files processed and matched patterns, 
to aid in tracking down unexpected matches.
That's a lot of text to stdout, so consider redirecting to a file.
"""

# import locale
import re
import sys
from importlib import import_module
import plac
from valetrules.manager import VRManager
from nlpcore.tseqsrc import TokenSequenceSource


# Base class. Not really necessary, but WTH.
class Matches(object):
    pass

# This is used for deduplication of matches.
# Best to use Python 3.7 or above so that (a) the iteration order is 
# deterministic, and (b) it's the insertion order. 
# That way the behavior is similar to using a list, so that if we choose 
# not to sort, we get the insertion order with both dict and list.
class MatchesDict(Matches):
    def __init__(self):
        self.dict = dict()

    def add(self, item):
        self.dict[item] = None

    def to_list(self):
        return list(self.dict.keys())

# This is used when we're not deduplicating.
# It probably wouldn't be radically less efficient just to always use dict?
class MatchesList(Matches):
    def __init__(self):
        self.list = list()

    def add(self, item):
        self.list.append(item)

    def to_list(self):
        return list(self.list)


# this reads the environment and inits the right locale
# https://stackoverflow.com/a/1318709/1778461
# locale.setlocale(locale.LC_ALL, "")

from nlpcore.projectsrc import PROJECT_SOURCES
for label, src in PROJECT_SOURCES.items():
    TokenSequenceSource.add_token_sequence_source(label, src)
source_types = TokenSequenceSource.available_type_labels()

def main(pattern_file: ("File containing definitions", "positional"),
         source_file: ("Name of the text source", "positional"),
         patterns: ("Names of the pattern to apply (space delimited)", "positional", None, str),
         sort: ("Sort", "flag", "s"),
         uniq: ("Deduplicate (unique)", "flag", "u"),
         target_type: ("Type of the input", "option", "y", str) = "text",
         aux_file: ("Auxiliary file", "option", "a", str) = None,
         added_import: ("Additional import", "option", "i", str) = None,
         nlp_engine: ("NLP module to use", "option", "x", str) = 'stanza',
         source_arguments: ("Extra args to provide to the token sequence source", "option", "g", str) = None,
         max_sources: ("Maximum number of sources (e.g., files) to process", "option", "m") = -1
         ):

    if added_import is not None:
        import_module(added_import)

    if nlp_engine == 'off':
        nlp_engine = None

    aux_args = {}
    if source_arguments is not None:
        for m in re.finditer(r'(\w+)=(\S+)', source_arguments):
            aux_args[m.group(1)] = m.group(2)

    data_source = TokenSequenceSource.source_for_type(
        target_type, source_file,
        aux_file=aux_file, nlp_engine=nlp_engine,
        **aux_args)

    vrm = VRManager()
    vrm.parse_file(pattern_file)

    pattern_names = re.findall(r'\S+', patterns)

    # Inform data source about the needed NLP requirements
    requirements = set()
    for name in pattern_names:
        requirements |= vrm.requirements(name)
    data_source.set_requirements(requirements)

    cls = MatchesDict if uniq else MatchesList

    matches = {}  # map pattern name to collection of match strings

    # Accumulate matches.
    source_cnt = -1
    for source, tseqs in data_source.token_sequences():
        source_cnt += 1
        if max_sources >= 0 and source_cnt >= max_sources:
            # sys.stderr.write("Stopping after %d sources\n" % source_cnt)
            break
        print(source)
        vrm.clear_recorded()
        for tseq in tseqs:
            for pattern in pattern_names:
                # I believe subsequent patterns will get the benefit of the 
                # annotation of the tseq that happens in the first pattern 
                # that needs to invoke the nlp_engine, which is a big 
                # efficiency boost. Nice design there.
                for match in vrm.scan(pattern, tseq):
                    text = match.matching_text()
                    print(pattern, text)
                    try:
                        matches[pattern].add(text)
                    except KeyError:
                        matches[pattern] = cls()
                        matches[pattern].add(text)

    # Write file per pattern.
    for pattern in pattern_names:
        with open(pattern + ".txt", "w") as f:
            if pattern not in matches:
                continue
            # texts = list(matches[pattern]).sort(key=locale.strxfrm)
            # texts = sorted(list(matches[pattern]), key=locale.strxfrm)
            texts = matches[pattern].to_list()
            if sort:
                # A, a, B, b, etc.
                texts = sorted(texts, key=lambda s: (s.lower(), s))
            for text in texts:
                f.write(text.replace("\n", "\\n"))
                f.write("\n")

plac.call(main)
