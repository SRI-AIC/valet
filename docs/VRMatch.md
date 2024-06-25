# Match classes

## Background

The match classes are primarily just containers for tracking the
extractions returned by various extractors.  Most of the interesting
information is stored in member variables (fields), though a few convenience
methods are provided for various purposes.  We document the most
salient member variables and methods, specifically those providing
access to other matches with which a match may be associated.

Internally, all matches of any language element are represented by 
instances of the `FAMatch` class and its subclasses.  All instances 
are indexed against tokens, recording the start and end tokens of 
a particular match.  

There are two ways in which two matches may be associated, 
via *incorporation* and *coordination*.  The former association 
is made when the pattern associated with a 
[phrasal extractor](VRPhraseExpressions.md) 
incorporates another named phrasal extractor by reference, 
(or when a [parse extractor](VRParseExpressions.md) 
incorporates another named parse extractor by reference). 
For example, consider the statement:

```
money -> $ @bignum
```

This defines a phrase extractor, called `money`, that looks for a
dollar sign followed by a phrase that matches another phrase
extractor, `bignum`, incorporated by reference.  Any `FAMatch` object
resulting from an application of `money` will carry information about
where `bignum` matched by pointing to another `FAMatch` object
internally.  Note that not all such references result in a submatch,
since they can occur in a sub-expression that's optional (e.g., is
followed by the `?` operator) or is one of several alternatives.  Note
also that the referenced extractors may themselves incorporate other
extractors by reference.  To gain access to the submatches generated
by those extractors, one typically needs to recurse, though we describe
a convenience function below that rolls all submatches into a flat
list.

The second association results from the application of 
[coordinator expressions](VRCoordinators.md), which by design can be 
arbitrarily nested.  Every sub-expression results in its own match stream, 
all of which are tracked in the top-level matches.  For example, 
consider the expression: 

```
near(litigation, 10, match(patent_number, _))
```

This asks for for matches of the `litigation` extractor, but only
those that occur within 10 words of some match of the `patent_number`
extractor.  Consequently, the resulting stream only consists of
matches for `litigation`.  However, internally these matches contain
pointers to the other matches to which the coordinator has associated
them.  In other words, each `litigation` match contains a pointer to
some `patent_number` match.

## FAMatch class

An `FAMatch` object has the following core member variables:

* `seq`: a reference to the `TokenSequence` object in which the match is found
* `begin`: the index of the first token in the matching phrase
* `end`: the index of the first token *after* the matching phrase, or the length of the token sequence if the match is coterminous with the end of the token sequence (but see note below)
* `submatches`: a list of matches extracted by extractors directly referenced by name
* `name`: if a match was returned by an extractor referenced by name, this field holds the name of the extractor

Note: There's a difference between how these matches are represented 
for phrasal matches and parse matches.  In phrasal matches, 
the `end` member variable points to the first token *after* the
tokens implicated in the match, exactly as described above.  However, 
in parse matches (see the `FAMatch` subclass `FAArcMatch` below), 
the end token is the token *at* the end of the matching dependency path.
In other words, for phrasal matches, the matched tokens are represented 
by `[begin,end)`-style indices, while for parse matches it's `[begin,end]`.

Moreover, for parse matches, the 'begin' value may be greater than, or 
equal to, the 'end' value, not just less than the 'end' value. 
While phrase expressions are always matched left-to-right in the token sequence, 
parse matches match edges in the dependency parse tree in a particular direction, 
either from parent to child or vice-versa, and the begin and end indices 
record the direction of the edge path as well as the tokens at either end 
of the edge path.

The following methods are provided:

* `get_extent(self)`: the token indices of the leftmost token and one past the rightmost token
* `start_offset(self)`: the character offset into the input text at which the match starts
* `end_offset(self)`: the character offset at which the match ends
* `matching_text(self)`: the verbatim matching string, as a phrase
* `all_submatches(self, name=None)`: all matches associated with any named subexpressions in the top-level extractor or any of its descendants

The `all_submatches` method optionally takes the name of a referenced
sub-extractor and returns only those submatches returned by that
sub-extractor.  Thus, if `m` is a match returned by the expression:

```
money -> $ @bignum
```

then the following call provides access to the `FAMatch` object
corresponding to the numeric portion of the match:

```
quantity = m.all_submatches('bignum')[0]
```

"FA" in `FAMatch` stands for "finite automaton". FAMatch instances 
are returned from phrasal expressions, which are implemented by 
finite automata. 

## FAArcMatch class

Instances of `FAArcMatch`, a subclass of `FAMatch`, are generated by parse expressions. 
They are functionally similar to `FAMatch` objects, differing in two key
respects, both already noted earlier:
* First, the 'end' field of a `FAArcMatch` contains the index of the
token *at* the end of the dependency path matched by the extractor, 
not of the first token *after* a matching phrase. 
* Second, as a result, it can be the case that the 'begin' index value 
is less than the 'end' index value, or that the 'begin' and 'end' indices 
are equal. (For more on this possiblity, see 
[parse expressions](./VRParseExpressions.md) and 
[Connects Operator](./VRCoordinators.md#connects-operator).)

Other than these differences, one can interact with these objects as
with `FAMatch` objects.  But note that the semantics of these matches
is quite distinct, as they point to the end points of paths through
the parse tree, jumping over intervening tokens in many cases.
One can infer from the [begin, end) values of `FAMatch`es 
returned from phrase expressions that the phrase rule matched all the 
tokens in that range. But `FAArcMatch` parse matches indicate that the 
parse rule matched some dependency tree path between the [begin, end] values, 
based on the tree edge label dependency strings, and currently there is 
no record kept of what that path was.

## CoordMatch class

Objects of the class `CoordMatch`, a subclass of `FAMatch`, are
generated by applying coordinator expressions.  In addition to the
standard fields of `FAMatch`, every `CoordMatch` object has an `op`
member variable that points to the object representing the coordinator
that produced it.  In addition, depending on the type and
parameterization of that coordinator, a `CoordMatch` may have
additional member variables pointing to coordinated matches.  The
relevant types are the same as documented in the
[page](VRCoordinators.md) on coordinator expressions.  Specifically,
we have the following types:

### Match expressions

Matches returned by [match-type](VRCoordinators.md#match-expressions)
coordinator operators, including `match` and `select`, always
include a `supermatch` field pointing to the match object against
which they were applied.  For example, if `m` is returned by the
expression:

```
match(my_extractor, _)
```

then `m.supermatch` refers to a `FAMatch` object that encompasses the
entire `TokenSequence`.

### Filter expressions

Matches returned by
[filter-type](VRCoordinators.md#filter-expressions) coordinator
operators, including `filter`, `prefix`, and `suffix`, may include a
`submatch` field pointing to the coordinated match that was used for
filtering.  This field will be absent if the operator was *inverted*,
if we requested matches that *do not* have the indicated coordinated
matches (because those matches don't exist). For example, consider the
expression:

```
nps_with_the ~ filter(has_the, match(noun_phrase, _))
```

The hypothetical expression finds noun phrases, then applies the
`has_the` extractor to each to retain only those that include the word
"the".  All resulting `CoordMatch` objects will have a `submatch`
field pointing to the corresponding match of the `has_the` extractor.
If we use the 'invert' keyword, we invert the filter, returning all noun
phrases that lack the word "the".  Consequently, no submatch exists.

### Proximal expressions

Matches returned by
[proximity-type](VRCoordinators.md#proximal-expressions) 
coordinator operators are similar
to filter-type matches.  They often have a `submatch` field pointing
to a match from the proximal stream.  For example, a match of the
expression:

```
near(litigation, 10, match(patent_number, _))
```

is a match of the `litigation` extractor found near some match of the
`patent_number` extractor.  The `submatch` field in such cases will
point to the proximal `patent_number` match.  Note that if the
expression is inverted, there will be no `submatch` field.

### N-ary expressions

Matches returned by [n-ary-type](VRCoordinators.md#n-ary-expressions)
coordinator operators, `union`, `inter` and `diff`, 
have a `submatches` member variable that points to a list of 
matches from the several subexpressions that are "unified", 
as follows.

The n-ary operators unify matches from the subexpressions 
into a single output match when the submatches have the same 
extent. The `submatches` field of the output match contains 
all the individual submatches with the same extent.
Note that these submatches will generally not be identical in 
respects other than their extent, since they typically are returned 
by distinct expressions.

Due to the varying definitions
of these operators, `union` matches of N subexpressions may have 
anywhere from 1 to N submatches, `intersection` matches will always 
have exactly N submatches, and `diff` matches will always have 
exactly 1 submatch. 

### Join expressions

Matches returned by [join-type](VRCoordinators.md#join-expressions)
coordinator operators, including `contains` and
`overlaps`, have `left` and `right` member variables that point to
matches from the two subexpressions that are "joined."

The `left` and `right` fields returned by the `contains` and
`overlaps` operators are also always non-`None`, and they typically
(though not necessarily) have distinct extents.

### Connect expressions

Matches returned by the [`connects` operator](VRCoordinators.md#connect-expressions)
each include `left`, `right`, and `submatch` fields.  The meaning of these fields is
probably best explained with an example:

```
connects(direct_object, match(meet, _), match(person, _))
```

This expression wants to find matches of `meet` and `person` that are
in a syntactic relation matched by the `direct_object` extractor,
which should correspond to a [parse expression](VRParseExpressions.md). 
The resulting match has the same extent as the match of the `direct_object` 
parse extractor, which is stored in the result match's `submatch` field.
The result match overlaps both the `meet` and `person` matches in extent 
and points to them in its `left` and `right` fields, respectively. 

## Frame class

Frame objects are a special subclass of match objects, and are generated 
by [frame rules](./VRFrames.md). 

A `Frame` object adds the following core member variables to the ones from 
`FAMatch`:

* `fields`: a dictionary mapping field names to a single `FAMatch` object 
   or a list of them

If there are no `FAMatch`es for a given field name, the field name will not 
be present in the dictionary.
