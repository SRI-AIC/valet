# Valet Rules API

## Background

This page documents the parts of the Valet Rules codebase most likely
to be of interest to users.

Two key classes used in Valet Rules are the `TokenSequence`
and the `FAMatch`.  Internally, the methods that implement extraction
all accept `TokenSequence` objects and most produce a `FAMatch` object or
stream of `FAMatch` objects. 

A `TokenSequence` represents arbitrary
segments of text, often, but not necessarily, a sentence, and records
the locations of words in the input, keeps track of any lexical
normalizations, and, optionally, maintains information about syntactic
categories and structure.  

A `FAMatch` is always in reference to some
`TokenSequence`, recording the start and end indexes of matching text
spans.  If a `FAMatch` is the result of an expression with named or
nested subexpressions, it tracks the submatches out of which it is
built, making it possible for the programmer to recover its
contributory elements.

An additional relevant class is the `Frame` class. `Frame` objects, rather 
than `FAMatch` objects, are produced by [frame extractors](./VRFrames.md). 
`Frame` objects gather up desired information about submatches in a more 
tailored and convenient way than `FAMatch` objects do. 

Note that access to these objects in code assumes that a number of
preparatory steps have been performed.  For an understanding of the
required steps, please consult the command-line script
[walkthrough](VRScriptWalkthrough.md).

## Contents

* [`TokenSequence`](VRTokenSequence.md)
* [`FAMatch`](VRMatch.md)
* [`Frame`](VRFrame.md)
