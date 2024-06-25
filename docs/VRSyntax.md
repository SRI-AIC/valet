# Valet Rules Syntax

## Pattern Definitions and Extractors

A Valet Rules (VR) model is typically defined in one or more source
files.  Each source file contains one or more named pattern definitions. 
These pattern definitions comprise the model.  VR
reads these pattern definitions and constructs a table associating the name of
a pattern definition with its executable representation.  Such an executable 
representation extracts text matching the pattern definition, and so is called 
an *extractor*.  Downstream code can
then ask VR to apply any of these named extractors to textual inputs
to find matches.

## Writing Pattern Definitions on File Lines

Pattern definitions always start at the left margin of a file line.  If a definition
is too long to fit on a single line, it can be continued on subsequent
indented lines.  In other words, any indented line will be considered
part of a definition started on a previous line.

If the line starts with a '#' character, it is considered a comment
and is not processed as part of a rule.

## Pattern Definition Syntax

All VR statements defining patterns have the following syntax:

```
<name> <delimiter> <binding>? <expression>
```

*Name* is a sequence of "word" characters, i.e.,
alphabetic, numeric, and the '_' character.  In addition, '.' can be a
component of names and has a special interpretation in connection with 
imported patterns (see Import Statement link below).  

The structure of the `<expression>` value depends on the type of pattern, 
which is signaled by the `<delimiter>` value, a special character sequence.

The following statement types are supported; note that names of statement 
types are linked to further documentation. 
Because statements can reference other statements, the statement types below 
are listed in the most logical order that best reflects the order in which 
those documentation sections should be read for ease of understanding.

|Statement Type|Delimiter| Pattern Example                                                              |
|----|---|----------------------------------------------------------------------------------------------|
|[Import](VRImports.md)|`<-`| `other_definitions <- /path/to/my/file`                         |
|[Token Test](VRTokenTests.md)|`:`| `article : { a an }`                                                |
|[Phrase](VRPhraseExpressions.md)|`->`| `np -> &article? &adj* &noun+`                       |
|[Parse](VRParseExpressions.md)|`^`| `prep_phrase ^ prep pobj`                               |
|[Coordinator](VRCoordinators.md)|`~`| `mycoord ~ near(prep_phrase, 5, np)`                  |
|[Frame](VRFrames.md)|`$`| `hframe $ frame(hiring, employer=hsubj name, employee=hobj name)` |

Note that there can be certain qualifiers attached to the left side of 
some of the basic delimiters shown above. For example, there is a case-
insensitive version of the `->` phrase statement delimiter, `i->`. 
These are described further in the relevant sections.

An optional [binding](VRBinding.md) qualifier, placed between the delimiter 
and the expression, supports on-the-fly rebinding of extractor names 
in the interest of greater rule modularity and re-use.

Pattern definitions may reference other named patterns defined earlier 
or later in the file, or defined in import statements defined earlier 
or later in the file.

Named pattern definitions may not recursively reference their own names, 
whether directly, or indirectly via the names of other patterns that 
directly or indirectly reference them. 
Doing so will generally cause recursion errors when the pattern is applied.


# Valet Rules Terminology

This document attempts to clarify the terminology used throughout the
documentation of Valet Rules, addressing the intended user, as someone
having at least modest familiarity with text analytics and natural
language processing.  The user should be comfortable and relatively
facile with Boolean expressions and, especially, regular expressions.
For certain features, it's also useful to know a little about natural
language syntax and parsing technology, in particular, dependency
grammars.  Sufficient knowledge of this subject may  be quickly
acquired by Googling "universal dependencies" and reading a few overviews.

Valet Rules applies **patterns** (or, equivalently, **rules**) to
text, yielding **matches**.  The general endeavor to which this exercise 
belongs is referred to as **information extraction**, though the term
also encompasses concerns not addressed by Valet Rules.  The key
representation of the input text is a **token sequence**, usually a
sequence of words interleaved with important forms of punctuation,
such as periods and commas.  This sequence can represent any unit of
text -- a sentence, a paragraph, a document -- though smaller units are
preferred, as they result in more efficient execution.  At its most
basic, a **match** is a subsequence of the input, represented
internally via pointers to the input sequence and the **begin** and
**end** tokens of the subsequence.  The **extent** of a match is 
defined to be the token range of the matched subsequence. 


The patterns that Valet Rules interprets are typically authored by a
human operator and encoded as **statements** in a **source file**.  As
these pages document, statements come in a number of forms, but always
pair a **name** and an **expression**.  In interpreting a source file,
Valet Rules associates the expressions with their names, enabling
downstream code to gain access to expressions by name.  The
programmatic object that maintains this association is called the
**manager**.  In typical use, one programmatically creates a manager,
asks it to parse a source file, then requests application of various
expressions by name to some input text.

Often, the thing that results from interpreting an expression, 
the thing that processes token sequences and returns matches, 
is referred to as an **extractor**.  Extractors come in multiple forms.
There are **token tests** (or just **tests**, defined by [token test
expressions](VRTokenTests.md)) that apply to individual tokens in the
input, and that only return matches of individual tokens.  There are
**phrase extractors** (defined by [phrase
expressions](VRPhraseExpressions.md)) that operate over sequences and
return matches that can span more than one token.  There are **parse
extractors** (defined by [parse expressions](VRParseExpressions.md))
that operate over the syntactic **parse tree**.  And there are
**coordinators** (defined by [coordinator
expressions](VRCoordinators.md)) that provide a layer of functionality
on top of the lower-level extractors.

A manager can be asked to apply an extractor to a token sequence and produce 
a **stream** (sequence) of matches.  All coordinators take at least one 
**input stream** (consisting of a sequence of **input matches**) and produce 
an **output stream** (consisting of a sequence of **output matches**).
Some coordinators also take the name of an extractor, which is applied
in some way to the input stream.  These are generally referred to as
**named extractors**, to distinguish them from stream expressions.
When this term is used, it typically refers to one of the parameters
of a coordinator, signalling that this parameter should be given an
extractor name.

## Submatch Capture and Selection

Because the concepts of **submatch capture** and **selection** are so key 
to the way Valet works, we will mention them here before presenting 
the specifics in other documentation sections, starting in the 
[Phrase Expression](VRPhraseExpressions.md) section.

Among other benefits, submatch capture allows you to define your rules 
in such a way as to allow matching of a referenced extractor 
**only when the match occurs _in a particular context_** defined 
by the referencing extractor. 
[Coordinator expressions](VRCoordinators.md) 
provide additional ways to achieve context-sensitive matching.

The [Phrase Expression](VRPhraseExpressions.md) section shows an example 
where a numeric money amount can be identified as such, and distinguished 
from non-money numeric occurrences, based on the numeric match occurring 
in the context of an immediately preceding dollar sign. 

The **general rule** of submatch capture and selection is that **submatches 
of any named extractor `ex2` referenced directly or indirectly by another 
named extractor `ex1` can be **_selected_** via the 
[coordinator expression](VRCoordinators.md) `select(ex2, ex1)`**.

Here **submatch** refers to a match of a referenced extractor 
(`ex2` in this case) obtained while matching the referencing extractor 
(here `ex1`). This lets you use `ex1` to define a context for `ex2` matches, 
and **access just those contextual submatches** via the select operator 
with `select(ex2, ex1)`, while still accessing **any** `ex2` matches 
irrespective of context via just the name `ex2`.

For example, in the phrase statement example from the table above, 
`np -> &article? &adj* &noun+`, matches of `np` will capture, as sub-matches, 
matches of `article`, `adj`, and `noun` that occur together in the 
sequence shown.

There are a few exceptions to the capture aspect of the above general rule. 
For example, submatches are not captured when token tests reference other 
token tests, nor when parse expressions reference token tests. Such captures 
would rarely be useful.
