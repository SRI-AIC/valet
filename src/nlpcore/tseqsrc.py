import os
import re
import sys
import traceback
from typing import List, Generator, Tuple

from .tokenizer import PlainTextTokenizer, TokenSequence
from .sentencer import Sentencer


class TokenSequenceSource(object):
    """
    Key method is token_sequences_from_text, which returns a list of 
    TokenSequence (or subclass) instances, where the text is first 
    semgented into sentences, then tokenized, and one TokenSequence 
    is returned per sentence.
    Also provides class methods for registering subclasses (or not) with 
    associated short string (eg specified as command line argument) 
    and constructing instances based short string value.
    Provides a small set of pre-registered subclasses."""

    # Fill in (replace) at end of file after classes are defined.
    source_types = {}

    @classmethod
    def source_for_type(cls, type_, source_name, aux_file=None, positive_label=None, rewrites=None, nlp_engine='stanza',
                        **kwargs):
        tsrc_cls = cls.source_types[type_]
        return tsrc_cls(source_name,
                        aux_file=aux_file, positive_label=positive_label, rewrites=rewrites, nlp_engine=nlp_engine,
                        **kwargs)

    @classmethod
    def add_token_sequence_source(cls, name, src):
        cls.source_types[name] = src

    @classmethod
    def available_type_labels(cls):
        return cls.source_types.keys()

    @classmethod
    def register(cls, child_cls):
        cls.add_token_sequence_source(child_cls.NAME, child_cls)

    def __init__(self, source_name,
                 token_regex=r'[a-z]+|[0-9]+|\S|\n|[ \t]+',
                 skip_initial_regex=r'[^a-zA-Z]+',
                 aux_file=None,
                 positive_label=None,
                 rewrites=None,
                 nlp_engine='stanza',
                 **kwargs
                 ):
        self.source_name = source_name
        self.token_regex = token_regex
        self.skip_initial_regex = skip_initial_regex
        self.aux_file = aux_file
        self.positive_label = positive_label
        self.rewrites = rewrites
        self.nlp_engine = nlp_engine
        self.tokenizer = self.get_tokenizer()
        self.sentencer = self.get_sentencer()

    def set_requirements(self, requirements):
        self.tokenizer.set_requirements(requirements)

    def get_tokenizer(self):
        return PlainTextTokenizer(preserve_case=True, token_regex=self.token_regex, nlp_on_demand=self.nlp_engine)

    def get_sentencer(self):
        return Sentencer(
            blank_line_terminals=True, tokenizer=self.tokenizer, skip_initial_regex=self.skip_initial_regex)

    def token_sequence_from_text(self, text) -> TokenSequence:
        return self.tokenizer.tokens(text)

    def token_sequences_from_text(self, text) -> List[TokenSequence]:
        """Return list of TokenSequence (or subclass) instances,
        one for each sentence as determined by self.sentencer."""
        result = []
        for sentence in self.sentencer.sentences(text):
            toks = sentence.tokens()
            result.append(toks)
        return result

    def token_sequences(self):
        raise NotImplementedError()

    def __len__(self):
        raise NotImplementedError()


# This seemed not to work correctly with vrgui.
# By bypassing parent's token_sequences_from_text, it bypassed the sentencer,
# but in the data were were using it with there could be multiple sentences
# per line.
# It might work OK if there's aways only one sentence per line,
# but it's probably normally best not to bypass the sentencer, just in case.
class PlainLinesSourceOrig(TokenSequenceSource):
    """Applies parent class's self.token_sequence_from_text method
    to lines from a single text file specified by self.source_name."""

    NAME = 'lines'

    def token_sequences_from_text(self, text):
        """Return list of TokenSequence (or subclass) instances,
        one for each line of text."""
        result = []
        for line in text.splitlines():
            if line == '':
                continue
            toks = self.token_sequence_from_text(line)
            result.append(toks)
        return result

    def token_sequences(self):
        """Generates a tuple for each line, with source name a combination of 
        self.source_name and a line index, and a list with a single token 
        sequence.
        TokenSequence."""
        fname = self.source_name
        with open(fname, "r") as fh:
            text = fh.read()
        count = 0
        for seq in self.token_sequences_from_text(text):
            yield "%s:%d" % (fname, count), [seq]
            count += 1

    def __len__(self):
        return 1  # TODO?


class PlainLinesSource(TokenSequenceSource):
    """Applies parent class's self.token_sequences_from_text method
    to lines from a single text file specified by self.source_name."""

    # TODO Make a variable for that return type?
    def token_sequences(self) -> Generator[Tuple[str, List[TokenSequence]], None, None]:
        """Generates a tuple for each line, with source name a combination of 
        self.source_name and a line index, and a list with token sequences 
        for the sentences on the line."""
        fname = self.source_name
        with open(fname, "r") as fh:
            text = fh.read()
        count = 0
        for line in text.splitlines():
            if line == '':
                continue
            seqs = self.token_sequences_from_text(line)
            if len(seqs) > 0:
                yield "%s:%d" % (fname, count), seqs
            count += 1

    def __len__(self):
        return 1  # TODO?


class PlainTextSource(TokenSequenceSource):
    """Applies parent class's self.token_sequences_from_text method
    to a single text file specified by self.source_name."""

    NAME = 'text'

    def token_sequences(self):
        """Generates a single tuple with self.source_name and a list of
        TokenSequence."""
        fname = self.source_name
        with open(fname, "r") as fh:
            text = fh.read()
        yield fname, self.token_sequences_from_text(text)

    def __len__(self):
        return 1


class StringTextSource(TokenSequenceSource):
    """Applies parent class's self.token_sequences_from_text method 
    to a single in-memory string, which is specified by self.source_name. 
    Contrast with PlainTextSource, which gets its text from a text file."""

    NAME = 'string'

    def __init__(self, source_name, real_source_name=None, **kwargs):
        super().__init__(source_name, **kwargs)
        if real_source_name == None:
            self.real_source_name = "String({})".format(source_name[0:50])

    def token_sequences(self):
        """Generates a single tuple with self.real_source_name and a list of 
        TokenSequence."""
        text = self.source_name
        yield self.real_source_name, self.token_sequences_from_text(text)

    def __len__(self):
        return 1


class CsvFileSource(TokenSequenceSource):
    """Applies parent class's self.token_sequences_from_text method
    to a single column of a single CSV file specified by self.source_name."""

    NAME = 'csv'

    # Could add additional args to pass to csv.reader() if more control 
    # is desired.
    def __init__(self, source_name, column_header=None, **kwargs):
        """column_header: header string of column to read from"""
        super().__init__(source_name, **kwargs)
        self.column_header = column_header

    def token_sequences(self):
        """Generates a single tuple with self.source_name and a list of 
        TokenSequence."""
        import csv
        fname = self.source_name
        with open(fname, "r") as fh:
            reader = csv.reader(fh)
            column_idx = None
            for rowi, row in enumerate(reader):
                if column_idx is None:
                    column_idx = row.index(self.column_header)
                    if column_idx < 0:
                        raise ValueError("No column named '%s' in header row '%s'" % (self.column_name, row))
                    continue
                text = row[column_idx]
                tseqs = self.token_sequences_from_text(text)
                if len(tseqs) == 0:
                    continue
                yield "%s:%d" % (fname, rowi), tseqs

    # Probably not too important to support this.
    # None of the CSV classes in projectsrc do.
    # We can implement it if someone wants it.
    # def __len__(self):
    #     return 1


class DirectorySource(TokenSequenceSource):
    """Applies parent class's self.token_sequences_from_text method
    to the text files in the self.source_name directory."""

    NAME = 'directory'

    def __init__(self, source_name, filter_regex=None, **kwargs):
        super().__init__(source_name, **kwargs)
        self.filter_regex = _safe_compile_regex(filter_regex)

    def token_sequences(self):
        """Generates pairs of filename and list of TokenSequence."""
        for fname in self.source_files():
            for item in self.token_sequences_from_file(fname):
                yield item

    def token_sequences_from_file(self, fname):
        """Generates pairs of filename and list of TokenSequence."""
        with open(fname) as fh:
            text = fh.read()
            tseqs = self.token_sequences_from_text(text)
            yield fname, tseqs

    # Note that currently the regex is applied to the filename, not the full path.
    def source_files(self):
        """Generates file paths for files in the self.source_name directory 
        (omitting dotfiles)."""
        dirname = self.source_name
        files = sorted([f for f in os.listdir(dirname) if not f.startswith('.')])
        for f in files:
            if self.filter_regex is None or re.search(self.filter_regex, f):
                yield "%s/%s" % (dirname, f)

    def __len__(self):
        return len(list(self.source_files()))


# Compile so that if there is a problem with the regex, we know up front 
# instead of getting an error on every filename we try to match.
def _safe_compile_regex(pattern):
    """If pattern is None or there is an error compiling it, return None."""
    if pattern is None:
        return None
    try:
        return re.compile(pattern)
    except Exception as e:
        print("Could not compile regex: '%s'. A Python regex is expected, not a glob pattern." % pattern, file=sys.stderr)
        traceback.print_exc()
        return None


class DirectoryTreeSource(DirectorySource):
    """Like the parent class but also recurses into subdirectories."""

    NAME = 'dirtree'

    # Note that currently the regex is applied to the full path, not the filename, 
    # which is different from the parent class behavior.
    def source_files(self):
        """Generates file paths for files in the self.source_name directory 
        and its descendant directories (omitting dotfiles)."""

        def _recurse(dirname):
            files = sorted([f for f in os.listdir(dirname) if not f.startswith('.')])
            for f in files:
                path = "%s/%s" % (dirname, f)
                if os.path.isdir(path):
                    for f2 in _recurse(path):
                        yield f2
                elif os.path.isfile(path):
                    if self.filter_regex is None or re.search(self.filter_regex, path):
                        yield path

        return _recurse(self.source_name)


# Predefined source type mapping.
TokenSequenceSource.source_types = dict(
    text=PlainTextSource,
    lines=PlainLinesSource,
    string=StringTextSource,
    csv=CsvFileSource,
    directory=DirectorySource,
    dirtree=DirectoryTreeSource
)

