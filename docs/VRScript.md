# A Valet Rules Command-Line Script

Below is the simple Python command-line script `vrcl.py`, which
can be used to experiment with Valet Rules on plain text data.  It has the following usage:

```
vrcl.py [-h] [-e | -m | -d | -c] [-t | -y (text|directory)| -x (stanza|spacy)] <pattern_file> <text_source> <pattern_name>
```
Arguments of `vrcl.py` are positional, with the following value types:

|Argument|Value Type|
|--------|----------|
|`<pattern_file>`|Name of a file containing ValetRules definitions|
|`<text_source>`|Name of a file or directory containing text files to process|
|`<pattern_name>`|Name of the pattern to apply|

Options for `vrcl.py` are as follow:

|Option|Long Option|Values|Description|
|------|-----------|------|-----------|
|`-h`|`--help`|N/A|Print a help message and exit|
|`-m` |`--markup`|N/A|The chosen action is to show markup|
|`-e` |`--extract`|N/A|The chosen action is to list extractions|
|`-d` |`--deppaths`|N/A|The chosen action is to show dependency paths|
|`-c` |`--conll`|N/A|The chosen action is to show CoNLL output|
|`-t`| `--trim`|N/A|With mark up show only matching lines|
|`-x <string>`| `--nlp_engine`|stanza<br>spacy|Select the NLP library (default is stanza)|
|`-y <string>`|`--target-type <text>`|text<br>directory|Identify the source as a file (default) or a directory of files|

The `<pattern_name>` argument value is a reference to a pattern named in the pattern
file.  The script finds the corresponding expression, evaluates it,
and applies it to the text in the specified file or files.
Application of the pattern yields different results, depending on the choice of action.  
  * If the action is `markup`, the script prints out the input file with simple markup showing where matches were found. If the optional `--trim` is also used, the output only contains lines containing matches.
  * If the action is `extract`, the output is a list of matching phrases.
  * If the action is `deppaths`, the script prints out the dependency paths. 
  * If the action is `conll`, the script produces CoNLL-style output for the `pattern_name`. For this action the script also accepts a space separated string of pattern names.

See the [script itself](../scripts/vrcl.py) for comments describing setup and API calls.
See the [GUI Tool](VRGui.md) for information about an interactive tool.

## Examples
Using the samplerules and sampletext files found in this (docs) directory, here are some examples as run from the top of the delivery hierarchy.

Extract and print just the tokens that match the `money` pattern specified in the sample rules
```bash
python scripts/vrcl.py -e docs/samplerules docs/sampletext money
SOURCE: docs/sampletext
['$1.13', '$1,130,000', '$1,025,393', '$104,607', '$18,833', '$1,100,726', '$29,274', '$18,833']

```

Mark up the tokens that match the `money` pattern and print out only those lines that contain tokens that match.
If the `-t` flag were omitted, the entire input text would be emitted.
```bash
python scripts/vrcl.py -m -t docs/samplerules docs/sampletext money
SOURCE: docs/sampletext
stock are valued at  >>> $1.13 <<<  per share, equal to the publicly traded share price
on the Effective Date, are capitalized in the amount of  >>> $1,130,000 <<<  and
The gross carrying amount was  >>> $1,025,393 <<< , accumulated amortization was
 >>> $104,607 <<<  and quarterly amortization expense was  >>> $18,833 <<<  as of December 31,
2016. The gross carrying amount was  >>> $1,100,726 <<< , accumulated amortization was
 >>> $29,274 <<<  and quarterly amortization expense was  >>> $18,833 <<<  as of December 31,

```
Extract and print just the tokens that match the POS annotation identified by the `propnoun` rule specified in the sample rules.
Note that by default this command would use the Stanza NLP package.  Use the `-x` flag to choose the spaCy library for annotations.
```bash
python scripts/vrcl.py -e -x spacy docs/samplerules docs/sampletext propnoun
SOURCE: docs/sampletext
['August', 'Effective', 'Date', 'ABC', 'License', 'Acme', 'Business', 'Company', 'LLC', 'ABC', 'U', '.', 'S', '.', 'Combination', 'Local', 'Thing', 'ABCD', 'Patent', 'ABC', 'License', 'ABC', 'Companys', 'February', 'Effective', 'Date', 'December', 'December']

```

Print out the token and dependency path information for tokens that match the `money` rule.
Note that the dependency path wording  is slightly different depending on which NLP library is used.
```bash
python scripts/vrcl.py -d -x spacy docs/samplerules docs/sampletext money
SOURCE: docs/sampletext
[['nmod']] $1.13
[['nmod']] $1,130,000
[['nmod']] $1,025,393
[['nmod']] $104,607
[['nmod']] $18,833
[['nmod']] $1,100,726
[['nmod']] $29,274
[['nmod']] $18,833

python scripts/vrcl.py -d docs/samplerules docs/sampletext money
SOURCE: docs/sampletext
2020-07-30 16:07:13 INFO: Loading these models for language: en (English):
=========================
| Processor | Package   |
-------------------------
| tokenize  | ewt       |
| pos       | ewt       |
| lemma     | ewt       |
| depparse  | ewt       |
| ner       | ontonotes |
=========================

2020-07-30 16:07:13 INFO: Use device: cpu
2020-07-30 16:07:13 INFO: Loading: tokenize
2020-07-30 16:07:13 INFO: Loading: pos
2020-07-30 16:07:14 INFO: Loading: lemma
2020-07-30 16:07:14 INFO: Loading: depparse
2020-07-30 16:07:15 INFO: Loading: ner
2020-07-30 16:07:16 INFO: Done loading processors!
[['nummod']] $1.13
[['nummod']] $1,130,000
[['nummod']] $1,025,393
[['nummod']] $104,607
[['nummod']] $18,833
[['nummod']] $1,100,726
[['nummod']] $29,274
[['nummod']] $18,833

```

Print out conll-style output based on a series of rule patterns.  
Only a portion of the output is shown here as it contains all tokens.
```bash
python scripts/vrcl.py -c docs/samplerules docs/sampletext "mamt notmoney"
SOURCE: docs/sampletext
    ...
quarterly              O
amortization           O
expense                O
was                    O
$                      O
18                     B-mamt
,                      I-mamt
833                    I-mamt
as                     O
of                     O
December               O
31                     B-notmoney
,                      O
2015                   O
.                      O

```

Extract and print matches from all files in a directory.  This assumes that all files are text files.
Each source file will generate separate output.
Only a portion of the output is shown here.
```bash
python scripts/vrcl.py -e -y directory  docs/samplerules docs docref
SOURCE: docs/VRAPI.md
['VRScript.md', 'VRTokenSequence.md', 'VRMatch.md']

SOURCE: docs/VRCoordinators.md
['VRPhraseExpressions.md', 'VRPhraseExpressions.md', 'VRParseExpressions.md']

SOURCE: docs/VRImports.md
[]
   ...
SOURCE: docs/ValetRules.md
['VRUsage.md', 'VRScript.md', 'VRGui.md', 'VRTerminology.md', 'VRSyntax.md', 'VRImports.md', 'VRTokenTests.md', 'VRPhraseExpressions.md', 'VRParseExpressions.md', 'VRCoordinators.md', 'VRAPI.md', 'VRTokenSequence.md', 'VRMatch.md']

SOURCE: docs/samplerules
[]
```





