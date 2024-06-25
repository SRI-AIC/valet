# The TokenSequence class

## Background

A common first step in any form of NLP is to convert a language input
into a sequence of atomic observations.  These are often "words," but can
include other language artifacts, such as punctuation.  The
observations in the sequence may be subject to various forms of
normalization, depending on the application, such as case
normalization, stemming, contraction splitting, stopword removal,
etc., each of which reduces the resemblance of the internal
representation to the text a human sees on the page.  The purpose of
the `TokenSequence` class (defined in the `nlpcore` package) is to span 
this divergence.  Code that uses
`TokenSequence` conveniently sees an array of strings, each
representing a normalized lexeme, but once individual words or word
spans are selected by that code, the `TokenSequence` provides the
information needed to identify the corresponding textual regions in
the input.

## TokenSequence class

This is accomplished entirely through member variables.  A
`TokenSequence` provides no methods that do much of value for
downstream code.  Instead, it's the static accounting stored in six
key fields that provide all the value:

* `text`: the text out of which the object was created, a string
* `offset`: the starting character offset of the portion of text that was tokenized
* `length`: the length in characters of the tokenized portion of text
* `tokens`: an array of strings, each corresponding to a "word" in the input
* `offsets`: an array of integer character offsets into `text` recording where each word starts (these offsets are added to the `offset` value)
* `lengths`: an array of the integer character lengths of each word

As this implies, the `tokens`, `offsets`, and `lengths` arrays are all
of the same length in a well-constructed `TokenSequence`.

When treated as a standard sequence in code, a `TokenSequence` serves
as a thin layer over its `tokens` field. In other words, it can just be
treated as a list of words by code that has no need for access to the
text from which they were derived.  For example, if `tokseq` refers to
a `TokenSequence`, then `tokseq[3]` returns the word at index 3.

## AnnotatedTokenSequence class

Syntax and other forms of derived information, such as named entity
constituency, are recorded in an `AnnotatedTokenSequence`, a subclass
of `TokenSequence`.  The implementation of the
`AnnotatedTokenSequence` class is beyond the scope of this document.
In all contexts of interest, it should be possible to treat instances
of this class as `TokenSequence` objects.  Whether one sees such
instances typically depends on whether external NLP tools have been
applied to the input.
