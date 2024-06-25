# Coordinators

The phrase pattern language makes it easy to *cascade* extractors,
incorporating one extractor as a component of a higher-level extractor
through a named reference.  However, this direct incorporation for
sub-matching affords downstream only a very limited means for
coordinating the application of distinct extractors to a given token
sequence.  *Coordinators* provide a much more flexible mechanism for
combining extractors or dissecting their matches.

One simple example in which this is useful has already been presented.
The presentation of [phrase expressions](VRPhraseExpressions.md) showed
how to cascade phrase extractors to implement an extractor for monetary
expressions:

```
# A number token
num : /^\d+$/

# A numeric expression, possibly with commas and/or decimal point
bignum -> &num ( , &num ) * ( . &num ) ?

# A currency recognizer
money -> $ @bignum
```

It was noted that, in principle, downstream code has access to the 
`bignum` portion of any match of `money`, but didn't explain how 
this could be achieved.  It is always possible to interact with the 
[`Match`](VRMatch.md) objects that result from the application of 
the `money` extractor using the Python [API](VRAPI.md), but a coordinator 
expression achives this access within the rule language itself, which is 
far more convenient:

```
money_amount ~ select(bignum, match(money, _))
```

This expression nests one coordinator expression in another.  The inner
expression `match(money, _)` generates a *stream* (sequence) of matches 
of the `money` extractor as applied to the token sequence. 
The [select](VRCoordinators.md#select-operator)
operator then converts this stream of matches to the submatches of
`bignum` they contain, essentially selecting the numeric part of the
monetary expression.

As this example suggests — and as with other language constructs —
coordinator expressions produce streams of matches.  Unlike other
language constructs, they also consume match streams, mediating among
and transforming input streams.

## Coordinator Syntax

A coordinator pattern definition has the form:

```
<name> ~ <expression>
```

The expression portion of the statement obeys the following grammar:

```
<coord_expression> -> '_'
                    | <extractor>
                    | <match_expression>
                    | <filter_expression>
                    | <proximal_expression>
                    | <nary_expression>
                    | <join_expression>
                    | <connect_expression>

<coord_expression_sequence> -> <coord_expression> | <coord_expression> ',' <coord_expression_sequence>

<match_expression> -> <match_op> '(' <extractor> ',' <coord_expression> ')'
<match_op> -> 'match' | 'select'

<filter_expression> -> <filter_op> '(' <extractor> ',' <coord_expression> ')'
                     | <filter_op> '(' <extractor> ',' <coord_expression> ',' 'inverted' ')'
<filter_op> -> 'filter' | 'prefix' | 'suffix'

<proximal_expression> -> <proximal_op> '(' <extractor> ',' <proximity> ',' <coord_expression> ')'
                       | <proximal_op> '(' <extractor> ',' <proximity> ',' <coord_expression> ',' 'inverted' ')'
<proximal_op> -> 'near' | 'precedes' | 'follows'

<nary_expression> -> <nary_op> '(' <coord_expression_sequence> ')'
<nary_op> -> 'union' | 'inter' | 'diff'

<join_expression> -> <join_op> '(' <coord_expression> ',' <coord_expression> ')'
<join_op> -> 'contains' | 'overlaps'

<connect_expression> -> <connect_op> '(' <extractor> ',' <coord_expression> ',' <coord_expression> ')'
<connect_op> -> 'connects'

<extractor> -> <identifier>             # The name of some extractor
<proximity> -> <non_negative_integer>   # A distance in number of tokens
```

Note that the `&` and `@` characters used in token test, phrase, and parse 
patterns when referencing other named patterns are neither required nor 
permitted in coordinator expressions.
(The purpose of those referencing characters in phrase and parse patterns is 
to disambiguate references from literals, but there is no place for literals
in coordinators, so such disambiguation is not necessary.)

## Coordinator Descriptions

As implied by the above grammar, Valet Rules supports the following types of
coordinator expression:

* [Underscore expression](#underscore-expression)
* [Extractor expressions](#extractor-expressions)
* [Match expressions](#match-expressions)
* [Filter expressions](#filter-expressions)
* [Proximal expressions](#proximal-expressions)
* [N-ary expressions](#n-ary-expressions)
* [Join expressions](#join-expressions)
* [Connect expressions](#connect-expressions)

#### Table of Coordinators

|Family|Name|# Input Streams|Filter?|Summary|
|---|---|---|---|---|
|[Underscore](#underscore-expression)|[underscore](#underscore-expression)|zero|no|matches full extent of each token sequence|
|[Extractor](#extractor-expressions)|[extractor](#extractor-expressions)|one|no|syntactic sugar for match operator|
|[Match](#match-expressions)|[match](#match-operator)|one|no|matches of extractor within extent of stream matches|
|[Match](#match-expressions)|[select](#select-operator)|one|no|matches of extractor recorded as submatches by stream matches|
|[Filter](#filter-expressions)|[filter](#filter-operator)|one|yes|matches from stream for which extractor matches within extent of stream match|
|[Filter](#filter-expressions)|[prefix](#prefix-operator)|one|yes|matches from stream that have an immediately preceding extractor match|
|[Filter](#filter-expressions)|[suffix](#suffix-operator)|one|yes|matches from stream that have an immediately following extractor match|
|[Proximal](#proximal-expressions)|[near](#near-operator)|one|yes|matches from stream that have a preceding or following extractor match|
|[Proximal](#proximal-expressions)|[precedes](#precedes-operator)|one|yes|matches from stream that have a preceding extractor match|
|[Proximal](#proximal-expressions)|[follows](#follows-operator)|one|yes|matches from stream that have a following extractor match|
|[N-ary](#n-ary-expressions)|[union](#union-operator)|≥ one|no|all matches from all streams (but see description for a detail)|
|[N-ary](#n-ary-expressions)|[inter](#intersection-operator)|≥ one|first|matches from first stream that have the same extent as a match from each other stream|
|[N-ary](#n-ary-expressions)|[diff](#diff-operator)|≥ one|first|matches from first stream that do not have the same extent as any matches from any of the other streams|
|[Join](#join-expressions)|[contains](#contains-operator)|two|first|matches from first stream that contain a match from second stream|
|[Join](#join-expressions)|[overlaps](#overlaps-operator)|two|first|matches from first stream that overlap a match from second stream|
|[Connect](#connect-expressions)|[connects](#connects-operator)|two|no|matches of parse extractor with one end in a match from each input stream|

#### Extent

The "extent" of a match simply refers to the range of tokens covered by a match, 
from the leftmost token through the rightmost token in the token sequence. 
(Different kinds of match instances in the [API](VRAPI.md) may represent 
this differently internally, as described in the discussion of the 
[`Match`](VRMatch.md) object types.)

#### Filters

The term "filter" is used in two senses. First, there is a family of operators 
we call the "filter" family (as in the "Family" column of the table and the 
`<filter_expression>` in the grammar). But more generally, we describe an operator 
as being a "filter" (as in the "Filter?" column of the table) if always generates 
matches that have the same extent as (typically a subset of) the matches in its 
input stream. In addition, a filter will always generate at most one output stream match 
for each input stream match.

Conceptually, some matches from the input stream are "passed through" the filter 
while others are blocked. In practice, from an [API](VRAPI.md) standpoint, 
new match object instances are generated, but they always have the same extent 
as the nominally passed-through input stream matches, and those input stream 
matches are stored as submatches of the new match instance. 

### Underscore Expression

The underscore expression `_` represents a match stream that 
wraps each token sequence in the input in a [`Match`](VRMatch.md) object.
That is, each token sequence generates a single match that has 
the full extent of the token sequence.
This serves as the base kind of coordinator expression, 
from which other coordinator expressions can be built up.

### Extractor Expressions

Extractor expressions generate a match stream by applying 
the named extractor to the base input stream, represented by `_`, 
using the match operator (which is described in the next section).

That is, a coordinator expression of the form 

```
<extractor>
```

is shorthand for and completely equivalent to 

```
match(<extractor>, _)
```

**Example**

The pattern presented earlier

```
money_amount ~ select(bignum, match(money, _))
```

may be more concisely written as

```
money_amount ~ select(bignum, money)
```

> **Note**
>
> Don't let this convenient shorthand obscure the distinction between 
> `<extractor>` and `<coord_expression>` in the grammar, though.
> Coordinator operator arguments are typed, as in the the grammar rule
>
> ```
> <match_expression> -> <match_op> '(' <extractor> ',' <coord_expression> ')'
> ```
>
> and while you can specify an extractor name for the second argument, 
> that's only because an extractor name is allowed by the grammar as 
> a coordinator expression, allowing this convenient shorthand. 
> The converse is not true; you can't use 
> any of the other coordinator expression types as an `<extractor>` 
> argument; an extractor name is required.
> 
> For example, 
> 
> ```
> money_amount ~ select(match(bignum, _), match(money, _))
> ```
> 
> is not a valid pattern, because the first argument to the select operator 
> must be an extractor name, not a full coordinator expression, 
> as shown in the `<match_expression>` grammar rule above (since both `match` 
> and `select` are `<match_op>`s).

### Match Expressions

Match expressions serve to generate a match stream by applying a named
extractor to the input stream.  There are two match operators:

* [Match operator](#match-operator)
* [Select operator](#select-operator)

#### Match Operator

**Basic Form**

```
match(<extractor>, <stream>)
```

This operator accepts an input stream of matches and produces a stream
of all matches of `<extractor>` textually contained within matches
in the input.

**Example**

```
match(my_extractor, _)
```

This is a simple invocation of `my_extractor` against the base match stream.
The matches returned from this coordinator would be have the same extent 
as the matches from `my_extractor` itself, which might be the name of 
a token test, phrase expression, parse expression, coordinator, or 
frame pattern. 

Instead of being directly associated with the `my_extractor` pattern, 
these coordinator matches would be associated with the coordinator pattern.  
In addition, the matches of `my_extractor` would be recorded as 
[submatches](VRSyntax.md#submatch-capture-and-selection)
of the coordinator matches, and could be accessed via 
a `select` coordinator expression.

Thus far, defining such a coordinator adds no real benefit over the
original extractor `my_extractor`, because its matching behavior against
the base match stream `_` (consisting of one match encompassing each token
sequence) is essentially the same as the behavior of the the original
extractor, which is applied to each token sequence. 

The power of coordinators comes by replacing the base match stream `_`
in the example with the output stream from one of the other kinds of
coordinator expression, *cascading* the coordinators. Here this would
restrict the scope of the `match` operator to the subsequences of the
token sequence represented by the output matches of that coordinator
expression. 

That all sounds complicated when written out, but an example should
make it clear. 

```
match(my_extractor, match(my_other_extractor, _))
```

This would return matches of `my_extractor` that are textually contained 
within matches of `my_other_extractor`, anywhere such matches exist.

#### Select Operator

**Basic Form**

```
select(<extractor>, <stream>)
```

The select operator produces a stream of all 
[submatches](VRSyntax.md#submatch-capture-and-selection)
corresponding to `<extractor>` in the input match stream.  For the product 
of this expression to be non-empty, the input stream typically must be the
result in part of the application of some extractor referencing
`<extractor>` as a component.  

The overview of [phrase extractions](VRPhraseExpressions.md) provides 
an explanation of how this referencing is accomplished for phrase 
expressions. Submatches are also produced by `<extractor>` references 
in coordinator expressions, as mentioned in the 
section above on the `match` operator, and this is the case for 
all coordinator operators (except `select` itself), not just for `match`. 

The difference between `match` and `select` is that `match` actually 
performs a matching operation, whereas `select` does not. `select` 
only retrieves submatches recorded during matching of some pattern that 
references another pattern.

In selecting from [frame matches](VRFrames.md), names of frame fields 
may also be used in place of the `<extractor>` name. 
(In case of fields that use the same name as patterns, both the field 
match and any submatches within the frame anchor matches and field 
matches are returned.)

**Example**

```
select(subextractor, match(extractor, _))
```

In this example, `extractor` is called on the input token sequences.
This expression selects any submatches for which `subextractor` is
responsible.  This example assumes that `subextractor` was referenced
in the definition of `extractor`.

### Filter Expressions

Filter family expressions filter the input match stream based on whether a
named extractor matches the text in or adjacent to an input match.  There are
three filter family operators:

* [Filter operator](#filter-operator)
* [Prefix operator](#prefix-operator)
* [Suffix operator](#suffix-operator)

#### Filter Operator

**Basic Form**

```
filter(<extractor>, <stream> [, inverted] )
```

The filter operator produces a match stream containing a subset of the
matches in `<stream>` by applying the extractor named by
`<extractor>`.  The behavior of this coordinator is modulated by the
optional `inverted` keyword argument.  If this argument is not present,
this operator will pass through any match in its input within
which `<extractor>` finds a match.  In essence, this operator treats
each matching fragment as a miniature token sequence, looking for a
match of `<extractor>` within its boundaries.  If 'inverted' is indicated,
its function is inverted: it passes through any matches within which
`<extractor>` fails to find a match.

The `filter` operator is similar to the `match` operator.
For both, the operator looks for matches of `<extractor>` within the 
extent of `<stream>` matches. The main difference is that the `match` operator 
returns matches with the extent of the `<extractor>` matches, while 
the `filter` operator returns matches with the extent of the `<stream>`
matches. Also, while `match` can return	multiple `<extractor>` matches per	
`<stream>` match, `filter` will only pass through one `<stream>` match
regardless of how many `<extractor>` matches occur within it.

**Example**

```
has_the : { the }
nps_with_the ~ filter(has_the, match(noun_phrase, _))
```

In this example, we imagine that we have defined an extractor for
English noun phrases.  We use the token test `has_the` to select those
noun phrases that use the word 'the'.

#### Prefix Operator

**Basic Form**

```
prefix(<extractor>, <stream> [, inverted])
```

Arguments to the `prefix` operator are identical to those for
`filter`.  However, instead of searching within the boundaries of an
input match, it passes through any for which `<extractor>` finds a
match immediately preceding the input when `inverted` is not specified.

**Example**

```
prefix(dollar_sign, match(number, _))
```

With appropriately defined extractors, this expression would return a
stream of numeric expressions preceded by a dollar sign.

#### Suffix Operator

**Basic Form**

```
suffix(<extractor>, <stream> [, inverted])
```

This coordinator is identical to `prefix`, except it filters on the
text following an input match.

### Proximal Expressions

Proximal operators filter the input match stream based on whether a named
extractor matches the text near an input match.  There are three proximity 
operators.

* [Near operator](#near-operator)
* [Precedes operator](#precedes-operator)
* [Follows operator](#follows-operator)

#### Near Operator

**Basic Form**

```
near(<extractor>, <proximity>, <stream>, [, inverted])
```

The named `<extractor>` is applied to the text in the vicinity of each
match in `<stream>`, and passes through any matches in the input for
which some proximal match of `<extractor>` is found.  

The width of the
search is controlled by the integer parameter `<proximity>`, which
specifies the number of tokens on either side of an input match to
scan.  For example, if `<proximity>` is 5, the `near` operator will
consider 5 tokens before and after an input match.  That is, if there is 
a match of `<extractor>` ending 0 to 5 tokens before a match from `<stream>`, 
or starting 0 to 5 tokens after a match from `<stream>` (0 tokens indicating 
adjacency), the `<stream>` match will be passed through. 

As with the filter operator, the `inverted` keyword can be used to invert the behavior of this operator.
When specified, this operator passes through
input matches for which a proximal match is *not* found.

**Example**

```
near(litigation, 10, patent_number)
```

We imagine that we have an extractor that recognizes references to
patents, and apply a second extractor designed to recognize mentions
of litigation activity in an attempt to find patents subject to
litigation.  In this case, we are considering the sentence context
consisting of 10 words on either side of the patent reference.

#### Precedes Operator

**Basic Form**

```
precedes(<extractor>, <proximity>, <stream> [, inverted])
```

Identical in behavior to the `near` operator, except it only considers
preceding context. The `precedes` operator with `<proximity>` of 0 
is equivalent to the `prefix` operator.

#### Follows Operator

**Basic Form**

```
follows(<extractor>, <proximity>, <stream> [, inverted])
```

Identical in behavior to the `near` operator, except it considers only 
trailing context. The `follows` operator with `<proximity>` of 0 
is equivalent to the `suffix` operator.

### N-ary Expressions

N-ary expressions unify any (nonzero) number of input match streams into 
a single output stream.  There are three n-ary operators:

* [Union operator](#union-operator)
* [Intersection operator](#intersection-operator)
* [Diff operator](#diff-operator)

Some of the n-ary expressions are also filter expressions, in the sense that 
they filter the first input match stream based on whether there are matches 
in the subsequent input match streams that are or are not coincident with 
each match in the first input match stream. 
`inter` and `diff` are filter operators in this sense; `union` is not.

To avoid misconceptions, note that, being filters, the filter operators
in this family return matches with the same extent as the matches from 
the first stream. In particular, the extents of the matches that they return
are *not* based on the intersection of the *extents* of the stream matches, 
nor the difference of those extents, etc. 
While the union operator is not a filter operator, neither are the returned
matches of the union operator based on the union of the extents.

#### Union Operator

**Basic Form**

```
union(<stream1>, <stream2>, ..., <streamN>)
```

The `union` operator creates an output stream that contains all matches 
in any of its input streams, except that multiple input stream matches 
with the same extent are unified into a single output match that contains 
all those input stream matches as submatches.

**Example**

```
union(match(verbal_relation, _), match(nominal_relation, _))
```

Here, we imagine that we have two relation extractors, one based on
verbal expressions of a particular relation and one based on nominal
expressions.  In this case, we've created a stream that contains both
verbal and nominal expressions.

#### Intersection Operator

**Basic Form**

```
inter(<stream1>, <stream2>, ..., <streamN>)
```

The `inter` operator passes through any matches found in all input
streams, in the sense that they have the same extent.  Note that the
streams will typically have been generated through different
means, and the matches they contain in general will have different
internal structure.  For example, any named submatches in either
stream will typically differ.  In practice, this operator returns
matches in `<stream1>` that have the same extent as at least one match
in all of `<stream2>, ..., <streamN>`.  When such coincidence of all extents 
is found, the matches from all the streams are recorded as submatches 
of the output match, and are accessible via the `select` operator.

#### Diff Operator

**Basic Form**

```
diff(<stream1>, <stream2>, ..., <streamN>)
```

The `diff` operator passes through any matches from the first stream *not* 
found in any of the other streams, in the sense of having the same extent. 

### Join Expressions

Join expressions unify two input match streams into a single output
stream.  There are two join operators:

* [Contains operator](#contains-operator)
* [Overlaps operator](#overlaps-operator)

The join expressions are both filter expressions, in the sense that 
they filter the first input match stream based on whether there is a match 
in the second input match stream that is contained by, or overlaps with, 
each match in the first input match stream. 

Being filters, the filter operators in this family return matches 
with the same extent as the matches from the first stream. In particular, 
the extents of the matches returned by the the overlaps operator are *not* 
based on the overlaps of the *extents* of the first and second stream matches.

#### Contains Operator

**Basic Form**

```
contains(<stream1>, <stream2>)
```

This operator is like `inter`, but applies a looser test of
equivalence between matches from the respective streams.  It passes
through any match from `<stream1>` whose extent is the same as or
encloses the extent of some match from `<stream2>`.  Subordinate
matches from `<stream2>` are recorded in output matches.

Note that it is not necessary to have a `contained_by` operator, 
as the effect of a hypothetical `contained_by(b, a)` expression 
can be achieved by either of the the following expressions:

```
match(b, a)
select(b, contains(a, b)) 
```

(Since both `match` and `select` require their first argument to be 
a pattern name rather than an expression, if the desired `b` is an 
expression, one can use that expression to define a named pattern, 
and the name can then be used in `match` or `select`.)


#### Overlaps Operator

```
overlaps(<stream1>, <stream2>)
```

An even looser test of equivalence than `contains`, but otherwise
similar.  The `overlaps` operator passes through any match from
`<stream1>` whose extent overlaps with the extent of some match from
`<stream2>`, recording the subordinate match from `<stream2>` in the
resulting output match.

### Connect Expressions

Connect expressions accept two input match streams and produce a
combined output stream based on whether a named extractor connects
them.  There is one connect operator:

* [Connects Operator](#connects-operator)

#### Connects Operator

**Basic Form**

```
connects(<extractor>, <stream1>, <stream2>)
```

The `connects` operator provides a means to combine extractors defined
against the parse tree, via [parse expressions](VRParseExpressions.md), 
with [phrase-level](VRPhraseExpressions.md) matches.  It considers all pairs 
of matches in the two input streams, producing an output match for any pair for 
which `<extractor>` (which is typically a parse extractor, but need not be) 
matches a path with start and end points in the *respective* pair members. 
When such a path is found, this expression returns the
match of `<extractor>` that enabled the connection.  These
match objects record the constituent input matches they connect
for access via `select` or downstream programmatic use.

Note the word *respective* above. While symmetrical parse expressions alone 
will produce matches in both directions, the `connects` operator only matches 
paths starting in the `<stream1>` match and ending in the `<stream2>` match, 
not vice-versa. The `connects` operator is not symmetric in those two arguments.

Note that when the extractor named by the `<extractor>` argument
is a [parse extractor](VRParseExpressions.md) (the most common
and useful usage), the resulting match objects behave like parse 
extractor matches.  In particular, depending
on how the extractor is defined, they can proceed right to left.

**Examples**

```
direct_object ^ dobj
met_person ~ connects(direct_object, match(meet, _), match(person, _))
```

Here, we imagine that we have an extractor recognizing verbal
expressions that express meeting events, called `meet`, and an
extractor recognizing references to people, called `person`.  The
parse expression `direct_object` connects a transitive verb to the
head noun in its direct object.  The `met_person` coordinator attempts
to answer who was met in a meeting event.  In the sentence, "The
deputy minister met Mike Pompeo," this expression should produce a
match that connects "met" with "Pompeo," provided the constituent
extractors are sufficiently robust.

```
cheeseburger : { cheeseburger }i
fries : { fries }i
prep_pobj ^ prep pobj
pobj_prep ^ pobj prep
conn0  ~ connects(prep_pobj, match(cheeseburger, _), match(fries, _))
conn0x ~ connects(prep_pobj, match(fries, _), match(cheeseburger, _))
conn1  ~ connects(pobj_prep, match(fries, _), match(cheeseburger, _))
```

This example illustrates the non-symmetry of the `connects` operator.
The parse tree fragment for the phrase "cheeseburger with fries" might look 
as shown below. In this case, `conn0` and `conn1` would match, but `conn0x`
would not. Also, the `conn0` match would start with "cheeseburger" and end 
with "fries" (left to right in the phrase "cheeseburger with fries"),
while the `conn1` match would start with "fries" and end with "cheeseburger"
(right to left).

```
- cheeseburger NN dobj
  - with IN prep
    - fries NN pobj
```
