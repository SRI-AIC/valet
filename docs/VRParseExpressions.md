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

Note that different NLP engines (Valet Rules supports at least two) 
may parse sentences slightly differently, and use different edge labels.

## Expression grammar

A parse expression is defined with the following syntax:

```
<name> ^ <expression>
```

The grammar defining legal expressions is the same as for 
[phrase expressions](docs/VRPhraseExpressions.md). 
Only the interpretation differs.  Whereas the elements
of a phrase expression align to tokens or words in the input, the
elements of a parse expression align to the labels in the dependency
parse.  A match is found between two tokens if a path connecting them
can be found in the dependency parse and the sequence of edge labels
matches the expression.  Note that this path can (and often does)
consist of both child-to-parent and parent-to-child edges.  The
matching procedure is currently insensitive to edge directionality.

Just like for phrase expressions, [token tests](docs/VRTokenTests.md)
may be used in parse expressions. Such tests will be applied to the
dependency parse edge labels. (This capability can help, to some degree,
with writing patterns in a way that abstracts over the differences between
the different NLP engines that Valet Rules can use.)

## Example

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

Here's a textual visualization of the parse tree that may help with understanding this example.

```
wanted (root)
- Rita (nsubj)
- buy (xcomp)
  - to (aux)
  - apple (obj)
    - an (det)
```

The path from `Rita` to `apple` goes upward in the tree from `Rita` via an `nsubj` edge 
to `wanted` (the root), then down via an `xcomp` edge to `buy` and from there down 
via a `obj` edge to `apple`. Hence the edge path is `nsubj`, `xcomp`, `obj`.
