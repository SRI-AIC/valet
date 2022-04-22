# Valet

## Requirements

* Python 3, with PIP
* [Conda](https://docs.conda.io/en/latest/miniconda.html) (or other environment management tool)


## Installation

### Run only (with access to SRI GitLab)

If you plan on using valet rules, but **NOT** to actively develop it, then follow these steps to install ValetRules:

```bash
pip install .
python3 -m spacy download en_core_web_sm
```

### Development

> We recommend the use of a (development) environment management tool like [Conda](https://docs.conda.io/en/latest/miniconda.html). Please note that `pip install` uses the `-e` flag in `pip install -e`, which will set your pip-installation to point to the local version of ValetRules.

```bash
cd VALETRULES_PROJECT_DIR
conda create --name valet python=3.8
conda activate valet
pip install -e .
python3 -m spacy download en_core_web_sm
pip install stanza
python -c 'import stanza; stanza.download("en")'
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

alternatively you may also run the unit tests with: `python -m unittest discover -s tests`

## Documentation

There is extensive documentation in Markdown format in the [docs](docs) directory. 
The entry point of the documentation tree is [Valet Rules](docs/ValetRules.md).

## Development Tips
1. NLP Engine Choice  
The `nlpcore` dependency for ValetRules supports two NLP engine libraries, Stanza and spaCy.  The scripts default to Stanza but support setting the choice through a parameter.  As a practical matter, Stanza performs more slowly than spaCy and tends to have higher precision.  You might consider developing rules with spaCy before transitioning to Stanza once the rules are established and you begin testing across broader input.  For more information on the annotations and dependencies available:  
  - [Stanza](https://stanfordnlp.github.io/stanza/neural_pipeline.html)
  - [spaCy](https://spacy.io/usage/linguistic-features)
2. Developing Rules  
The [GUI tool](docs/VRGui.md) provides a way to develop rules and examine the annotations and dependencies in source text interactively. It can be helpful to work within the GUI until you are getting the desired results from one or two source files before using the developed rules across a much broader set of source files with the [command line tool](docs/VRScripts.md).  
3. Adapting the Tokenizer  
The `nlpcore` library used by ValetRules provides text tokenization and sentence segmentation. While ValetRules is primarily intended to be used on 
this type of tokenization and segmentation, if you want to modify  how the tokenizer works, such as to maintain spaces or newlines, you would need to create a new tokenizer class by subclassing from the existing examples found in the NLP Core source `tokenizer.py` file.


## Contact

The original author and lead developer of the Valet package is Dayne
Freitag (daynefreitag@sri.com, daynef@gmail.com).

