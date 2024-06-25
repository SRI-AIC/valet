"""
Defines pre-annotated source types.
"""

import re
from io import StringIO
from typing import List, Generator, Tuple

import conllu

from nlpcore.dbfutil import GenericException
from .fssrc import FileSource, DirectorySource, DirectoryTreeSource
from .tokenizer import TokenSequence, AnnotatedTokenSequence
from .tseqsrc import TokenSequenceSource


###############################################################################


# Note there can be multiple documents in CONLL text files.
# One motivation for moving the token_sequences_from_text method
# (along with the sentencer and tokenizer) out of TokenSequenceSource
# into a new subclass PlainTokenSequenceSource that ConllUFileSource
# does not inherit from, is that that method's signature doesn't provide
# for multiple List[TokenSequence] nor an output source name,
# the way token_sequences does.


class ConllUStringSource(TokenSequenceSource):
    """
    Like StringTextSource but expects text to be in CONLL-U format
    rather than plain text.
    """

    NAME = 'conllu_string'

    def __init__(self, source_name, **kwargs):
        kwargs["nlp_engine"] = None
        super().__init__(source_name, **kwargs)

    def __len__(self):
        return 1  # TODO

    def token_sequences(self) -> Generator[Tuple[str, List[TokenSequence]], None, None]:
        """Generates a tuple for each document in the text."""

        text = self.source_name

        # This does all the work of parsing.
        sentences = conllu.parse(text)

        all_doc_sentences = self.group_sentences_by_doc(sentences)

        # Generate token sequences for each doc.
        for i, doc_sentences in enumerate(all_doc_sentences):
            docid = doc_sentences[0].metadata["newdoc id"] if "newdoc id" in doc_sentences[0].metadata else i
            id_ = f"{docid}"
            yield id_, self.token_sequences_for_one_document(doc_sentences)

    def group_sentences_by_doc(self, sentences):

        # Find where the docs start.
        doc_start_indices = [i for i, sentence in enumerate(sentences)
                             if "newdoc id" in sentence.metadata
                             or "newdoc" in sentence.metadata]
        if len(doc_start_indices) > 0:
            if doc_start_indices[0] != 0:
                # There's a partial doc at the start, or no doc markers at all.
                doc_start_indices.insert(0, 0)
        else:
            doc_start_indices.append(0)
        doc_start_indices.append(len(sentences))

        # Group the sentences by doc.
        all_doc_sentences = []
        for d in range(0, len(doc_start_indices))[0:-1]:
            doc_sentences = sentences[
                            doc_start_indices[d]:doc_start_indices[d + 1]]
            all_doc_sentences.append(doc_sentences)

        return all_doc_sentences

    # TODO? Look for newpar/NewPar paragraph indicators, and add newline chars.
    def token_sequences_for_one_document(self, doc_sentences) -> List[TokenSequence]:
        """Return list of TokenSequence (or subclass) instances,
        one for each sentence as determined by the CONLL-U format."""

        # Build up CSV-style lists of lists for each sentence with
        # [start, length, token, num_spaces].
        # Also build up shared "fake" text from the tokens and intervening
        # spaces.
        csv_sentences = []
        strings = []
        # last_end = 0
        for sentence in doc_sentences:
            csv_sentence = []
            start = 0  # relative to start of sentence
            for ctoken in sentence:
                token = ctoken['form']
                length = len(token)
                misc = ctoken['misc']
                spaces = " " if (misc is None or "SpaceAfter" not in misc or misc["SpaceAfter"] != "No") else ""

                # TODO Run this code on some CONLL-U corpus and look at
                # any cases like these.
                if " " in token:
                    print(f"Space char in token '{token}' in sentence '{sentence}'")
                if "_" == token:
                    print(f"Token is underscore or missing in sentence '{sentence}'")

                # We only use len(spaces) for last token, in next section
                # below, FWIW.
                csv_sentence.append([start, length, token, len(spaces)])
                strings.append(token)
                strings.append(spaces)
                start += length + len(spaces)
            csv_sentences.append(csv_sentence)
        string = "".join(strings)

        # Build the AnnotatedTokenSequences, with no annotations yet.
        result = []
        offset = 0
        for csv_sentence in csv_sentences:
            starts, lengths, tokens, num_spaces = zip(*csv_sentence)
            length = starts[-1] + lengths[-1]  # not counting spaces between sentences
            tseq = AnnotatedTokenSequence(
                text=string, tokens=list(tokens),
                offsets=list(starts), lengths=list(lengths),
                offset=offset, length=length,
                nlp_on_demand=None, tokenizer=None)
            # Incr offset for next sentence, but account for likely space after last token.
            offset += length + num_spaces[-1]
            result.append(tseq)

        # Add the annotations.
        for i, sentence in enumerate(doc_sentences):
            tseq = result[i]
            self.add_token_annotations(tseq, sentence)
            self.add_dependencies(tseq, sentence)

        return result

    def add_token_annotations(self, tseq, sentence):
        """Add pos, tag, lemma (no ner) info from the sentence to the tseq."""
        pos = [None for _ in tseq]
        tag = [None for _ in tseq]
        lemma = [None for _ in tseq]
        ner = [None for _ in tseq]

        for j, ctoken in enumerate(sentence):
            if ctoken['xpos'] is not None:
                pos[j] = ctoken['xpos']
            if ctoken['upos'] is not None:
                tag[j] = ctoken['upos']
            if ctoken['lemma'] is not None:
                lemma[j] = ctoken['lemma']

        if any(x for x in pos if x is not None):
            tseq.add_annotations('pos', pos)
        if any(x for x in tag if x is not None):
            tseq.add_annotations('tag', tag)
        if any(x for x in lemma if x is not None):
            tseq.add_annotations('lemma', lemma)

    def add_dependencies(self, tseq, sentence):
        """Add dependency info from the sentence to the tseq."""
        deps = []
        for j, ctoken in enumerate(sentence):
            child = j
            # CONLL-U uses 1-based token ids with 0 = root,
            # while nlpcore uses 0-based with -1 = root,
            # so we can just subtract 1 from the CONLL parent id.
            parent = ctoken['head'] - 1
            deptype = ctoken['deprel']
            # Unlike the Spacy/StanzaAnnotator code, we don't have to
            # align to our own tokenizer, since we don't have one.
            deps.append((child, parent, deptype))
        tseq.add_dependencies(deps)


class ConllUFileSource(ConllUStringSource):
    """
    Like PlainFileSource but expects text to be in CONLL-U format
    rather than plain text, and can generate multiple tuples,
    one for each document in the file.
    """

    NAME = 'conllu_file'

    def __init__(self, source_name, *, encoding="utf-8", **kwargs):
        super().__init__(source_name, **kwargs)
        # Most kwargs are probably intended for TokenSequenceSource,
        # but some might be for the fssrc.
        # Let each decide what applies to it.
        self.fssrc = FileSource(source_name, encoding=encoding, **kwargs)

    def token_sequences(self) -> Generator[Tuple[str, List[TokenSequence]], None, None]:
        """Generates a tuple for each document in the file."""

        for path, text in self.fssrc.texts():

            # This does all the work of parsing.
            sentences = conllu.parse(text)

            all_doc_sentences = self.group_sentences_by_doc(sentences)

            # Generate token sequences for each doc.
            for i, doc_sentences in enumerate(all_doc_sentences):
                docid = doc_sentences[0].metadata["newdoc id"] if "newdoc id" in doc_sentences[0].metadata else i
                id_ = f"{path}:{docid}"
                yield id_, self.token_sequences_for_one_document(doc_sentences)

    # TODO? Note that since there can be multiple documents in each file,
    # this generally WON'T return the number of items generated
    # by token_sequences.
    def __len__(self):
        return len(self.fssrc)


class ConllUDirectorySource(ConllUFileSource):

    NAME = 'conllu_directory'

    def __init__(self, source_name, *, encoding="utf-8", filter_regex=None, **kwargs):
        super().__init__(source_name, **kwargs)
        self.fssrc = DirectorySource(source_name, encoding=encoding, filter_regex=filter_regex, **kwargs)


class ConllUDirectoryTreeSource(ConllUFileSource):

    NAME = 'conllu_dirtree'

    def __init__(self, source_name, encoding="utf-8", filter_regex=None, **kwargs):
        super().__init__(source_name, **kwargs)
        self.fssrc = DirectoryTreeSource(source_name, encoding=encoding, filter_regex=filter_regex, **kwargs)


###############################################################################


# This was something I did as mostly as a proof of concept and a stepping stone
# to the CONLL classes.
# Leaving it in for now in case we want to adapt it later for formats that
# specify token offsets.
# FWIW, it doesn't have any concept of a document boundary.

class SimpleFileSource(TokenSequenceSource):
    """
    Like PlainDirectorySource but expects files to be in my simple pre-tokenized
    format rather than plain text.
    """

    NAME = 'simple_file'

    def __init__(self, source_name, **kwargs):
        super().__init__(source_name, **kwargs)
        self.fssrc = FileSource(source_name)

    # TODO? Should I reset offsets so initial one is 0, if it's not already?
    # Otherwise we'll have that many spaces at the start of the shared text
    # string.
    def token_sequences(self) -> Generator[Tuple[str, List[TokenSequence]], None, None]:
        """Return list of TokenSequence (or subclass) instances,
        one for each sentence as determined by the simple format."""

        # Raise exception if the offsets are not valid.
        # Or move this to the simple_sentences function?
        def check(line, start, length, token, last_end) -> None:
            msg = None
            if start < last_end:
                msg = f"start = {start} < {last_end} = last_end in line '{line}'"
            elif length < 1:  # can't have a 0-len token?
                msg = f"length = {length} < 1 in line '{line}'"
            elif len(token) != length:
                msg = f"length = {length} != len('{token}') in line '{line}'"
            if msg is not None:
                raise GenericException(msg)

        for path, text in self.fssrc.texts():

            # Build up CSV-style lists of lists for each sentence with [
            # start, length, token], checking for offsets' validity.
            # Also build up shared "fake" text from the tokens and intervening
            # spaces.
            csv_sentences = []
            sentence_starts = []
            strings = []
            last_end = 0
            for sentence in simple_sentences(text):  # get next sentence
                csv_sentence = []
                for i, line in enumerate(sentence):
                    label, start, end, token = line.split("\t", 4)
                    start = int(start)
                    end = int(end)
                    length = end - start
                    check(line, start, length, token, last_end)

                    # Unlike my CONLL-U code, this is space before the token,
                    # not after.
                    num_spaces = start - last_end
                    if i == 0:
                        sentence_start = start
                        sentence_starts.append(sentence_start)
                    start -= sentence_start
                    csv_sentence.append([start, length, token])
                    last_end = end

                    if num_spaces > 0:
                        spaces = " " * num_spaces
                        strings.append(spaces)
                    strings.append(token)
                csv_sentences.append(csv_sentence)
            string = "".join(strings)

            # Build the AnnotatedTokenSequences, with no annotations yet.
            result = []
            for i, csv_sentence in enumerate(csv_sentences):
                starts, lengths, tokens = zip(*csv_sentence)
                offset = sentence_starts[i]
                length = starts[-1] + lengths[-1]  # not counting spaces between sentences
                tseq = AnnotatedTokenSequence(
                    text=string, tokens=list(tokens),
                    offsets=list(starts), lengths=list(lengths),
                    offset=offset, length=length,
                    nlp_on_demand=None, tokenizer=None)
                result.append(tseq)

            id_ = f"{path}"
            yield id_, result

    def __len__(self):
        return len(list(self.fssrc.source_files()))


#
# Adapting some code from BRAT's tools/anntoconll.py.
#

# EMPTY_LINE_RE = re.compile(r'^\s*$')
EMPTY_LINE_RE = re.compile(r'^$')
# VALID_LINE_RE = re.compile(r'^\S+\t\d+\t\d+.')
VALID_LINE_RE = re.compile(r'^\S+\t\d+\t\d+\t.')

def simple_sentences(text) -> Generator[List[str], None, None]:
    """Generate list of lines for one sentence from the text.
    Sentences are delimited by empty lines.
    """

    lines = []
    reader = StringIO(text)
    # while (line := reader.readline()) != "":  # still using 3.7; no :=
    line = reader.readline()
    while line != "":  # indicates EOF
        if line[-1] == "\n":  # strip one \n; last line may lack \n
            line = line[0:-1]
        # print(line)
        if EMPTY_LINE_RE.match(line):
            if lines:
                yield lines
                lines = []
        elif not VALID_LINE_RE.match(line):
            raise GenericException('Line not in valid format: "%s"' % line)
        else:
            lines.append(line)
        line = reader.readline()
    if lines:
        yield lines


class SimpleDirectorySource(SimpleFileSource):
    """
    Like PlainDirectorySource but expects files to be in my simple pre-tokenized
    format rather than plain text.
    """

    NAME = 'simple_directory'

    def __init__(self, source_name, **kwargs):
        super().__init__(source_name, **kwargs)
        self.fssrc = DirectorySource(source_name)


###############################################################################


# Add to predefined source type mapping.
def add_to_sources():
    for cls in [
            ConllUStringSource,
            ConllUFileSource,
            ConllUDirectorySource,
            ConllUDirectoryTreeSource,
            # SimpleFileSource,
            # SimpleDirectorySource,
            ]:
        TokenSequenceSource.register(cls)

# I'd like to call this from here, but code that goes through
# TokenSequenceSource.source_for_type, like valetrules.gui.gui,
# won't have imported this.
# I'd like to call it from the end of tseqsrc, but that would be
# a circular import.
# For now code that might use these sources has to call this,
# similar to what valetrules.gui.gui does for projectsrc.
# I'm adding a call to this there.
# add_to_sources()
