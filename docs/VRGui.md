# A Valet Rules GUI Tool

`vrgui` is a Python script to wrap Valet Rules capabilities into a GUI
designed for efficient authoring of extraction rules
(a.k.a. patterns). The tool can be used to experiment interactively
with Valet Rules on plain text data.  It has the following usage:

```
vrgui.py [-h] [ -y (text|directory)] [-x (stanza|spacy)] <pattern_file> <text_source>
```

for example:
```
$ python scripts/vrgui.py -y directory sofia.vrules ~/scm/gtl/sofia/sofia/data/fire-paragraphs-asfiles2
```

## Syntax

Arguments of `vrgui.py` are positional, with the following value types:

|Argument|Value Type|
|--------|----------|
|`<pattern_file>`|Name of a file containing ValetRules definitions|
|`<text_source>`|Name of a file or directory containing text files to process|

The most important optional arguments are `--target-type` and `--nlp-engine`.
The `--help` output above shows only the default values of all the
optional arguments.
Options for `vcgui.py` are as follow:

|Option|Long Option|Values|Description|
|------|-----------|------|-----------|
|`-h`|`--help`|N/A|Print a help message and exit|
|`-x <text>`|`--nlp_engine <text> `|stanza<br>spacy<br>off|Select the NLP library (default is stanza)|
|`-y <text>`|`--target-type <text>`|text<br>directory|Identify the source as a file (default) or a directory of files|
|`-a <filename>`| `--aux-file`|filename|Use as the annotation information for annotated table source type (default is None)|
|`-i <module>`| `--added_import`|modulename|Import additional Python module of this name (default is None)|
|`-t <file path>`| `--term-expansion`|path|Path to term expansion data file (default is None)|
|`-b <file path>`| `--embedding_file`|path|Path to file containing word embeddings (default is None)|
|`-g <string>`| `--source-arguments`|string|Extra args to provide to the token sequence source (default is None)|
|`-r <string>`| `--rewrites`|string|Standing text transformations (default is None)|
|`-v <float>`| `--scale_height`|float|Modify the vertical height of the window |
|`-f <int>`| `--font_size`|int|Modify the font size to use in the document and pattern panels |


The main choices for `--target-type` are `directory` and `text`. This
controls the interpretation of the `text_source` positional
parameter. The usual choice is `directory`. In this case, `vrgui` will
work with files from the specified directory, which will be treated as
text files in the system default encoding. An alternate choice is
`text`, in which case `vrgui` will work with just the single specified
`text_source`, again treated as a text file in the system default
encoding. (There may be additional choices available for files in
particular formats related to particular projects.)

The available choices for `--nlp-engine` are `stanza`, `spacy`, and
`off`. One of the Stanza and Spacy tools may be specified to provide
several NLP (natural language processing) capabilities leveraged by
`vrgui`. Specifically, these tools provide dependency tree parsing,
part-of-speech identification, lemma identification, and named entity
recognition. Certain `vrgui` capabilities rely on the presence of
these tools and the information they provide, but these tools are not
required if your patterns do not require that information.

Note that Stanza and Spacy have somewhat different behavior,
particularly in regard to the dependency tree parses they
generate. These differences can require your patterns to be written
differently to conform to whichever tool you choose. In many cases,
patterns can be written to work with either tool, but this requires
more effort.

## Description

The script will initialize by loading the designated text and parsing
the rules before bringing up a ValetRules console with two windows and
an information frame.

The top window will contain the contents of the pattern file and the
bottom window will contain the contents of the current text source.
The tool supports interactively experimenting with rules and seeing
matches in the text pane.  You can match across multiple text files
and you can save the updated contents of the rule pane back to the
pattern file.

It is recommended that you keep the terminal window (console) from
which you invoked `python` with `vrgui.py` visible to the side of the
GUI window, because error, debug, and other information will be
printed to the console.

## Usage

Selecting any individual rule will highlight matches in the text
pane. Selecting different rules changes which tokens are highlighted.
The information frame will show the name of the current text file and
the number of matches for the selected rule in that file.

You can experiment with rules interactively by manually editing the
contents of the rule pane.  You must hit the `Parse` button for the
system to see the update.

The `Save` button will write out any rule updates to the same file
that was used at startup. This will overwrite the existing file, so be
sure to create a copy if you want to keep a record of what existed.
This can be a helpful way to develop rules interactively.

Clicking on the name of a pattern in the top panel will match the
pattern against the sentences in the current document in the second
panel (document panel) of the GUI. (If the name of the pattern does
not have underlining when the mouse is moved over it, it is not valid
or has not yet been parsed.) Matches will be highlighted in a shade of
blue. While you can edit text in the document panel, it does not have
any lasting effect.

Clicking in the document panel will show information in the fourth
panel about the word clicked on. This includes the part of speech
(POS) of the word (noun, verb, etc), lemma (word stem), and any NER
(named entity recognition) information available.

Dragging the mouse in the document panel to select a range of text in
a sentence will show the path in the dependency parse tree of the
sentence between the first and last words selected. Currently, it will
also show a representation of the full parse tree of the sentence in
the console window.

The `Scan` button causes the selected rule to be matched against the
document(s) from the `text_source`. The scan will start with the first
document after the current document, and stop at the first document
with matching text, or stop again at the current document if no
matches are found. If you started up the tool with a directory as the
text source, clicking  on the `Scan` button will process the next
available text file in sequence for matches.  If the application was
started with just one source text file the single file is just
reprocessed.

The `Stop` button stops a scan that is in progress.

`Scan`ning again will continue from the next document after where the
last match was found, or where the last scan was stopped.

The `Next` button, rather than scanning through documents until a
match is found, will just move to the next document, whether or not
a match is found in it.
Whereas `Scan` is more useful in looking for "false positive" matches of
a rule, `Next` is helpful in looking for "false negative" non-matches.

The `Rewind` button will move back to the first document of the `text_source`.

The `Export` button is not enabled for text input and will print the
message: "Data Source has no export method".

The `Gather` and `Learn` buttons are experimental. These capabilities
are under development, and are not intended for you to use at this time.

See the [command line script](VRScript.md) for information about
command-line processing.

## Examples

Using the `samplerules` and `sampletext` files found in this (`docs`)
directory, here are some examples as run from the top of the delivery
hierarchy.

Run the tool using the sample rules and test provided with spaCy as
the chosen NLP engine.
Experiment by selecting the rule `noun` and see which items are highlighted.
Change the rule by removing `NNS` and hitting `Parse`. 
Then select the rule `noun` again and watch the highlighting change 
to no longer highlight plural nouns.
Note that if you hit `Save` you will overwrite the `samplerules` file.

```bash
python scripts/vrgui.py -x spacy docs/samplerules docs/sampletext
```

Run the tool using the sample rules but use the entire `docs` directory
as your source of text files. This command will use Stanza as the
default NLP engine.
Experiment by selecting the rule `money` and hitting `Scan` to process
each available file in turn. Select the checkbox and run the same
experiment.  Note that you don't see any files that have no matches.

```bash
python scripts/vrgui.py -y directory docs/samplerules docs
```

> Errors related to parsing patterns or applying them to documents may
  cause error output to the console from which `vrgui` was invoked. It
  is suggested to monitor that output, since error information is not
  shown in the GUI itself.
