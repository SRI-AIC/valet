# ValetRules

## Requirements

* Python 3, with PIP
* [Conda](https://docs.conda.io/en/latest/miniconda.html) (or other environment management tool)

## Installation

### Run only

If you plan on using ValetRules, but **NOT** to actively develop it, then follow these steps to install it:

```bash
pip install .
python3 -m spacy download en_core_web_sm
pip install stanza
python3 -c 'import stanza; stanza.download("en")'
```

### Development

> We recommend the use of a (development) environment management tool like [Conda](https://docs.conda.io/en/latest/miniconda.html). Please note that `pip install` uses the `-e` flag in `pip install -e`, which will set your pip-installation to point to the local version of ValetRules.

```bash
conda create --name valet python=3.8
conda activate valet
```

Then install ValetRules with pip's `-e` option:
```bash
pip install -e .
python3 -m spacy download en_core_web_sm
pip install stanza
python3 -c 'import stanza; stanza.download("en")'
```

## Tests

To run the unit and coverage tests, follow these instructions:

```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
python setup.py test
coverage run --source="src" -m unittest discover -s tests/
coverage report
coverage html
```

Alternatively, you may also run just the unit tests with:

```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
python -m unittest discover -s tests
````

## Documentation

There is extensive documentation in Markdown format in the [docs](docs) directory. 
The entry point of the documentation tree is [Valet Rules](docs/ValetRules.md).

## Development Tips

### NLP Engine Choice

The `nlpcore` package of ValetRules supports two NLP engine libraries, Stanza and spaCy.  The scripts default to Stanza but support setting the choice through a parameter.  As a practical matter, the ValetRules team has used Spacy more, and the tests that involve NLP are written to use rules that assume Spacy's style of providing NLP information, and the documentation tends to use Spacy style examples.

Both tools provide dependency tree parsing,
part-of-speech identification, lemma identification, and named entity
recognition. Certain ValetRules capabilities rely on the presence of one of
these tools and the information they provide, but these tools are not
required if your patterns do not require that information.

Note that Stanza and Spacy have somewhat different behavior,
particularly in regard to the dependency tree parses they
generate. These differences can require your patterns to be written
differently to conform to whichever tool you choose. In some cases,
patterns can be written to work with either tool, but this requires
more effort. The rule types that may be affected by NLP engine differences
are [token tests](docs/VRTokenTests.md)
and [parse expressions](docs/VRParseExpressions.md).
Other rule types are generally not affected.

For more information and details on the annotations and dependencies provided
by the tools:  
  - [Stanza](https://stanfordnlp.github.io/stanza/neural_pipeline.html)
  - [spaCy](https://spacy.io/usage/linguistic-features)

### Developing Rules

The [GUI tool](docs/VRGui.md) provides a way to develop rules and examine the annotations and dependencies in source text interactively. It can be helpful to work within the GUI until you are getting the desired results from a smaller set of source files before using the developed rules across a much broader set of source files with scripts such as the [command line tool](docs/VRScript.md).  

### Adapting the Tokenizer

The `nlpcore` package of ValetRules provides text tokenization and sentence segmentation. While ValetRules is primarily intended to be used on 
this type of tokenization and segmentation, if you want to modify  how the tokenizer works, such as to maintain spaces or newlines, you would need to create a new tokenizer class by subclassing from the existing examples found in the NLP Core source `tokenizer.py` file.

## Contact

The original author and lead developer of the Valet package is Dayne
Freitag (daynefreitag@sri.com, daynef@gmail.com).
