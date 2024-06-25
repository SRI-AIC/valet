# Valet Rules Binding

## Syntax

A binding qualifier takes the form:

```
[ name=newname (, ...)* ]
```


In other words, a binding qualifier is list of `id1=id2` within square
brackets.  When specified (always in the definition of a new extractor),
such a qualifier effects a *dynamic* rebinding of the indicated extractors
in the execution of the newly defined extractor.  All references to 
extractors named on the left-hand side of the list of name pairs are 
replaced with references to the corresponding extractors on the
right-hand side.  This happens at time of execution or application
and is in force across the entire call stack.  For example, consider
the following rule set:

```
my_test : &something
my_other_test : &something_else
my_extractor -> the red &my_test
my_coordinator ~ my_extractor
my_other_coordinator ~[my_test=my_other_test] my_coordinator
```
Here, `my_other_coordinator` is equivalent to `my_coordinator`, except that 
anywhere `my_test` might be used in the application of `my_coordinator`,
`my_other_test` is used instead.

## Example

The rebinding is mainly useful for repurposing or specializing library rules.
For example, consider the fragment:

```
article: [a and the]
adj: pos[JJ]
noun: pos[NN NNP]
pnoun: pos[NNP]
np -> &article? &adj* &noun+
```

Here, `np` implements a simple extractor for base noun phrases.  If we wish 
instead to extract the subset of noun phrases that involve proper nouns,
we can do so by rebinding the `noun` test:

```
pnp1 ->[noun=pnoun] @np
pnp2 ~[noun=pnoun] np
```

Both of these forms should achieve the desired effect through slightly
different means.

