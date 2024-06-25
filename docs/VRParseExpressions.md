# Parse Expressions

Parse expression are analogous to phrase expressions, but instead of
applying to the linear sequence of tokens in the input, they apply to the
edge labels of the tree produced by a dependency parser applied to the input.
Of course, a dependency parser must have been executed on the input for a
parse expression to be evaluated without error.  The mechanisms for
producing a dependency parse and associating it with the input is
beyond the scope of this documentation, but here is 
a description of the general idea: https://universaldependencies.org/introduction.html. 

To understand how these
expressions are applied, it's useful to know the form a parse takes.
A dependency parse is a tree with labeled edges in which nodes are
tokens.  Every node has exactly one parent in the tree and zero or
more children.  The child-parent relation reflects various types of
syntactic modification, the type signaled by the label of the edge.
For example, the node for an adjective modifying a noun will generally
be a child of the noun's node.
There is a an example of a textual visualization of a simple parse tree 
further below.

Note that different NLP engines (Valet Rules supports at least two) 
may parse sentences slightly differently, and use different edge labels.

## Expression grammar

A parse expression is defined with the following syntax:

```
<name> ^ <expression>
```

The grammar defining legal expressions is the same as for 
[phrase expressions](./VRPhraseExpressions.md). 
Only the interpretation differs.  Whereas the elements
of a phrase expression align to tokens or words in the input, the
elements of a parse expression align to the edge labels in the dependency
parse.  A match is found between two tokens if a path connecting them
can be found in the dependency parse and the sequence of edge labels
matches the expression.  Note that this path can (and often does)
consist of both child-to-parent and parent-to-child edges.

Just like for phrase expressions, [token tests](./VRTokenTests.md)
may be used in parse expressions. Such tests will be applied to the
dependency parse edge labels -- not to the document tokens. 
(This capability can help, to some degree,
with writing patterns in a way that abstracts over the differences between
the different NLP engines that Valet Rules can use.)

However, unlike in phrase expressions, 
only literal edge labels, or references to token tests or other parse 
expressions, are permitted in parse expressions. References to phrase, 
coordinator, or frame expressions are not permitted.

Whereas phrase expressions result in matches that are strictly left-to-right 
in the token sequence 
(i.e., the begin token necessarily precedes the end token), parse 
expressions potentially can yield matches over the edge label tree 
that proceed from right to left in the token sequence. 

For example, symmetrical expressions yield two matches, one in each direction.
The most common form such symmetrical expressions take are single-element
expressions.  For example, we may be interested in occurrences of the `dobj`
dependency to process direct-object relations between words.  Because
literal use of this dependency in a parse pattern does not specify edge
direction, Valet yields two matches for each corresponding edge -- one 
connecting a verb and its direct object, and one connecting the direct
object to its verb.  See below for how to restrict the direction of 
edge matches.

Moreover, whereas phrase expressions observe the standard greedy regular 
expression behavior and return only the longest possible match starting 
from any given token, parse expressions can return multiple matches, 
even in a single direction. 
Also, just as parse expressions can return multiple matches starting 
from a given token, matching edge labels, and ending at several other tokens, 
a parse match starting from a given token and ending at another token 
does not "consume" the labels and make the corresponding edges ineligible 
for inclusion in another match.
An example is given below.


## Examples

A simple example will make this more concrete.  To find
connections between the subject and object of the main verb in a
sentence or clause, the following pattern can be used:

```
svo ^ nsubj obj
```

Applying this pattern to the sentence `Rita bought an apple` will
yield a match connecting `Rita` to `apple` via the respective
dependencies of these two words on the main verb, `bought`.  However,
this pattern will fail to match the sentence, `Rita wanted to buy an
apple`, because in this sentence `Rita` depends on `wanted`, while
`apple` depends on `buy`.  The verb `wanted` has a `xcomp` dependency
on `buy`.  We can make a simple modification to our pattern to handle
both of these cases:

```
svo ^ nsubj xcomp ? obj
```

Here's a textual visualization of the parse tree that may help with 
understanding this example.

```
wanted (root)
- Rita (nsubj)
- buy (xcomp)
  - to (mark)
  - apple (obj)
    - an (det)
```

The path from `Rita` to `apple` goes upward in the tree from `Rita` 
via an `nsubj` edge expressions, to `wanted` (the root), then downward 
via an `xcomp` edge to `buy` and from there down via a `obj` edge 
to `apple`. Hence the edge path is `nsubj`, `xcomp`, `obj`.

An element in a parse expression may be qualified in order to restrict its 
application to upward or downward edges by prefixing it with a '/' or '\', 
respectively (without invervening whitespace).
Thus, we can enforce that an `nsubj` literal element only match upward edges
with the following modified pattern:

```
sv ^ /nsubj
```

Without the '/', this symmetric pattern would would yield two matches, 
from `Rita` to `wanted`, and the reverse from `wanted` to `Rita`; 
with the '/', the pattern yields only the single match from the child 
token `Rita` upward via the `nsubj` edge to its parent token `wanted`.

In the case of a token test reference rather than a literal, the syntax 
would be: 

```
nsubj : { nsubj }
sv ^ &/nsubj
```

Now consider another rule and sentence.

```
svos ^ nsubj xcomp ? obj conj*
```

```
wanted (root)
- Rita (nsubj)
- buy (xcomp)
  - to (mark)
  - apple (obj)
    - an (det)
    - orange (conj)
      - an (det)
    - pear (conj)
      - and (cc)
      - a (det)
```

Due to the non-greedy behavior of parse expressions, this will yield 
three matches, connecting `Rita` to each of `apple`, `orange`, and `pear`.


## Connects coordinator

Parse expressions are primarily useful in conjunction with the 
[connects coordinator](./VRCoordinators.md#connects-operator). 
