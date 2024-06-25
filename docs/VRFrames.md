# Frames

The Valet Rules statement types described so far allow you create individual
extractors of various kinds, to reference extractors from other extractors,
to select submatches from referenced extractors, and to use coordinators
to allow independent extractors to work together in various ways.

Another of the needs Valet Rules is designed to address is the extraction
of "frames" that gather up information from matches of related patterns
in a more tailored and convenient way than provided by submatches alone. 
This capability is provided by frame statements.

Suppose `nsubj` is a parse extractor matching subject-verb dependencies,
`dobj` is a parse extractor matching verb-object dependencies,
`name` is an extractor matching proper names, and `hire` is an extractor
matching words like `hire`, `hired`, and perhaps other forms or synonyms.
A typical frame usage is the following:

```
hsubj  ˜ select(hire, connects(nsubj, name, hire))
hobj   ˜ select(hire, connects(dobj, hire, name))
hiring ˜ union(hsubj, hobj)
hframe $ frame(hiring,
               employer=hsubj name,
               employee=hobj name)
```

Here the frame operator uses a previously defined
extractor `hire` as an anchor, then applies submatch selection
to associate contributing submatches with arbitrarily named fields 
`employer` and `employee`.
The `union` operator is used to combine the streams of hire matches that connect 
to either a hirer or a hiree, and combine the hire matches that connect to both. 
The frame then selects the respective submatches, treating each of the two slots 
as optional.
The submatch selection takes the form of a space-separated list of named
extractors, representing a kind of submatch selection path.

## Frame syntax

A frame statement has the form:

```
<name> $ <frame_expression>
```

The expression portion of the statement takes the form:

```
frame(<anchor_pattern>,
      <field_name>=<field_pattern> <field_pattern> ...,
      <field_name>=<field_pattern> <field_pattern> ...,
      ...)
```

The effect of evaluating a statement like this is to name a new type of
extractor and instruct the system how to build it out of previously
defined extractors.
The `<anchor_pattern>` and `<field_pattern>` elements should be the names
of other defined extractors, while the `<field_name>` elements can be
arbitrary identifiers.

The anchor pattern is special. A frame match is created for each match
of the anchor pattern within the token sequence being considered.
For each such anchor pattern match, and each named field, the specified
sequence of field patterns is applied using the
[select coordinator](./VRCoordinators.md#select-operator) to select
submatches. This starts by selecting submatches of the first field pattern
from the anchor match, then selecting submatches of those submatches
using the subsequent field patterns.
Any submatches of the final field pattern are associated with the field name.
It is permissible that no such submatches are found.

There are a few more points to note about the submatch selection process.
First, in the hiring example it would be possible to have a rule like

```
hframe $ frame(hiring,
               employer=name,
               employee=name)
```
because submatch selection is not limited to immediate submatches 
of a given match, but includes submatches of submatches, etc.

But the above rule would find the `name` rule matches for both the hirer
and the hiree (if both are mentioned), and associate _both_ matches with
both field names `employer` and `employee`. Being able to specify _sequences_
of `<field_pattern>`s gives the rule language the ability to zero in
on specific matches, as in the original version of the rule.

Second, because submatch selection is not
limited to immediate submatches, it is not necessary that the sequence
of `<field_pattern>` elements spell out the entire submatch path.
The above examples illustrate that as well. Including `hsubj` or `hobj`
in the `<field_pattern>` sequence is not _required_ to find `name`
submatches, but specifying these does allow finer control over which
are found.

Third, since is is permissible for field submatches not to be found,
the original rule also works in the case of sentences like
"McDonald's is hiring!" or "Tom Smith got hired yesterday.",
where only one of the hirer or hiree is mentioned. 
The `hframe` rule would generate a frame for these sentences,
but the matches associated with one of the fields (employee or employer, 
respectively) would be an empty set.

## Additional information

Frame matches are accessible via the [API](./VRAPI.md)
and via scripts such as `vrframes.py`.
[vrgui](./VRGui.md) will print the frame extractions to the terminal window
when the selected rule is a frame statement.
