# A Walkthrough of vrcl.py

## The `vrcl.py` Script

The entire `vrcl.py` script is shown below. Following the script, its key sections are discussed.  

```
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
         conll: ("Action: Produce CoNLL-style output", "flag", "c"),
         trim: ("Option: Only show matchine lines with mark up", "flag", "t"),
         nlp_engine: ("Option: Select specific NLP engine to use", "option", "x") = 'stanza',
         target_type: ("Option: Type of the input: {text, directory}", "option", "y", str) = "text"):

    if not (markup or extract or deppaths or conll):
        print("No useful action specified")
        exit()

    if nlp_engine == 'off':
        nlp_engine = None
    data_source = TokenSequenceSource.source_for_type(target_type, target, nlp_engine=nlp_engine)

    vrm = VRManager()
    vrm.parse_file(pattern_file)

    pattern_names = re.split(r'\s+', pattern_names)
    pattern_name = pattern_names[0]

    # Inform data source about the needed NLP requirements
    requirements = set()
    for name in pattern_names:
        requirements |= vrm.requirements(name)
    data_source.set_requirements(requirements)

    for source, tseqs in data_source.token_sequences():
        print("SOURCE:", source)
        if markup:
            data_markup = vrm.markup_from_token_sequences(pattern_name, tseqs, trim=trim != 0)
            print(data_markup)
        if extract:
            extractions = vrm.extract_from_token_sequences(pattern_name, tseqs)
            print(extractions)
        if deppaths:
            paths = vrm.dpaths_from_token_sequences(pattern_name, tseqs)
            for path, text in paths:
                print(path, text)
        if conll:
            output = vrm.conll_from_token_sequences(pattern_names, tseqs)
            print(output)
        print()
    
plac.call(main)    
```
## Imports

The Python `re` and the `plac` modules, which are used for convenience
in parsing command-line arguments.
Valet Rules provides the `manager` module and `nlpcore` is provided as a Valet Rules dependency.

```
from valetrules.manager import VRManager
from nlpcore.tseqsrc import TokenSequenceSource
```

As described in the section on [terminology](VRSyntax.md#valet-rules-terminology), the
manager object imported in the first line above is the primary entry
point into Valet Rules.  The other nlpcore import provides a utility class
to aid in converting the input text 
into the `TokenSequence` objects that Valet Rules expects.  It applies 
a Sentencer module, which implements a heuristic and imperfect approach
to segmenting a large body of text into individual sentences, 
but this is optional. One could instead create a single large `TokenSequence`
object representing the entire input document, though doing so would
typically lead to inefficiencies.
Note that all the objects created retain
pointers to the full text of the input document and know their
relative offsets within this document.  

## The `TokenSequenceSource` Module call

```
    data_source = TokenSequenceSource.source_for_type(target_type, target, syntax_annotation != 0)
```

After the data source is turned in to token sequences representing
sentences in the text file or files,  the manager is instantiated and processes
the source file containing the patterns. 
If the input pattern name is a quoted string containing multiple patterns, only the first word is used as the input pattern, except for the CoNNL output, which can handle multiple patterns.

```
vrm = VRManager()
vrm.parse_file(source_file)
pattern_names = re.split(r'\s+', pattern_names)
pattern_name = pattern_names[0]
```

## Markup and Extract Function Calls

Once these actions are completed, the manager can be asked to apply
the extractors named in turn to the token sequences associated with each source file or files, 
as follows:

```
for source, tseqs in data_source.token_sequences():
    print("SOURCE:", source)
    if markup:
        data_markup = vrm.markup_from_token_sequences(pattern_name, tseqs, trim=trim != 0)
        print(data_markup)
    if extract:
        extractions = vrm.extract_from_token_sequences(pattern_name, tseqs)
        print(extractions)
    if deppaths:
        paths = vrm.dpaths_from_token_sequences(pattern_name, tseqs)
        for path, text in paths:
            print(path, text)
    if conll:
        output = vrm.conll_from_token_sequences(pattern_names, tseqs)
        print(output)
    print()
```

The result of the markup function call is a single string -- the contents of the
text file with special syntax indicating where matches of the
extractor named by `pattern_name` were found.  Note that nothing
prevents the matches resulting from application of the extractor from
overlapping.  The markup function call discards overlaps, keeping the earliest
in a series of overlapping matches.  The result of the extract function call
is a list of strings, each corresponding to a different match.

The result of the extract function call is a list of extracted strings that match the pattern. 

The result of the deppaths function call is a dependency path and the associated text match.

The results ofthe conll function call is the output for all the space separated patterns given on the command line in conll-style output. 

