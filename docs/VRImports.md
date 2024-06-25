# Import Statements

Import statements or *imports* provide support for organizing the statements in a VR model by
type and intended use.  The typical usage is:

```
model <- /path/to/vrfile
```

When this statement is executed, the statements defined in `vrfile`
are evaluated and associated with the name `model`.  In all contexts
where extractors can be referenced by name, the extractors in this
external file can be referenced by prefixing them with `model.` 
(including the delimiter `.`, with no whitespace on either side 
of the `.`).

## Example

Thus, if `vrfile` defines an extractor `ext` and is imported with the statement above, 
statements elsewhere in the importing file can refer to the extractor as `model.ext`.
Note that because the references are evaluated at runtime, the import statement 
need not occur before the statement referencing the imported name.

`/path/to/vrfile`:
```
ext : { if and but }i
```

Importing file:
```
model <- /path/to/vrfile
ext : &model.ext
```

In this example, `ext` is defined in `vrfile` as a [token test](VRTokenTests.md) using the `:` syntax, and is referred 
to using the `&` syntax.  As in the example, direct reference to this test requires the `model.` prefix.  Because 
of this, our reuse of the `ext` name in the importing file causes no ambiguity.


## Multiple levels of imports

Multiple levels of imports are possible. For example:

`/path/to/baz.vrules`:
```
ext : { if and but }i
```

`/path/to/bar.vrules`:
```
baz <- /path/to/baz.vrules
```

`/path/to/foo.vrules`:
```
bar <- /path/to/bar.vrules
ext : &bar.baz.ext
```

## Absolute and relative pathnames

In the examples above, we used absolute pathnames, but relative pathnames are also supported.  When an import uses
a relative pathname, Valet attempts to resolve it in the following order:

- with respect to the current working directory (the directory from which the script invoking Valet was executed)
- with respect to the directory containing the current pattern file (i.e., the pattern file containing the import statement)
- with respect to an internal directory containing "built-in" pattern files.

The current implementation contains several built-in files, all of which provide commonly useful pattern:

- **ortho.vrules**: a set of general-purpose orthographic patterns that capture things such as capitalization, numeric expressions, etc.
- **syntax.vrules**: patterns capturing common syntactic categories and structures
- **ner.vrules**: patterns providing access to named entities

Developers interested in investigating available built-in patterns can review these files, which are stored in the
`data` directory of the source distribution.

## Namespace imports

There is another import syntax used to emulate use of an external file,
but without actually using an external file. As with external files,
the purpose is to organize the statements in a VR model.

## Example

```
noun_qual <-
  noun_governing_verb ~ select(verb, connects(object, verb, noun))
  noun_qual ~ diff(noun_qualifier, noun_governing_verb)

qualified_noun -> &noun_qual.noun_qual+ &noun
```

The meaning of these rules is beyond the scope of this discussion,
and not all related rules are shown, but these illustrate the syntax.

A "namespace import" block is indicated by the `<-` delimiter occurring
with no file path to its right.
The rules indented under the name and delimiter are treated as if they
occurred in an external file.

The same dot notation is used for referencing "namespace import" rules
defined in the block from outside the block; here, `noun_qual.noun_qual`.
In this example, the first occurrence of `noun_qual` is the import name, 
analogous to `model` in the external file import example. 
The second occurrence of `noun_qual` is the rule name, analogous to `ext`
in that earlier example.

## Resolution of rule names

Using imports substantially complicates the resolution of rule names. 

In the namespace import example above, the rules `verb`, `object`, 
`noun`, and `noun_qualifier` may be assumed to be defined in the 
same rules file, at the same level as `qualified_noun`, outside of 
the `noun_qual` namespace import block.

Rules inside that block can refer to rules outside that block 
(such as `verb`, `object`, and `noun`) but in the same file 
via unqualified (un-dotted) names.

(Indeed, for rules at top level in the same rule file, they generally
must be referenced with unqualified names. The exception would be
if that rules file were itself imported into another one, which
opens up additional possibilities, as discussed below.)

When resolving a rule reference, whether qualified or not, it is first
looked up in the innermost scope, whether a file import scope or 
a namespace import scope, and if not found, successively in enclosing 
scopes.

`noun_governing_verb' referenced by the `noun_qual` rule defined in the 
`noun_qual` scope is first looked up in that scope, and is found there.
`verb`, `object`, and `noun` referenced from the `noun_qual` scope
are also first looked up in that scope, but they are not found.
In that case, they are next looked up in the surrounding scope, that
of the present rules file, and are (assumed to be) found there.

However, it's also possible for the present rules file to have been
imported into another rules file. In that case, if `verb`, `object`, 
and `noun` are not found in the present rules file, they will be 
looked up in the surrounding scope of the importing rules file. 

This is a highly dynamic rather than lexical resolution scheme, 
which does open up possibilities for unintended rule resolution, 
so be aware of that.
