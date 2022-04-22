# Import Statements

Import statements or *imports* provide support for organizing the statements in a VR model by
type and intended use.  The typical usage is:

```
model <- /path/to/vrfile
```

When this statement is executed, the statements defined in `vrfile`
are evaluated and associated with the name `model`.  In all contexts
where extractors can be referenced by name, the extractors in this
external file can be referenced by prefixing them with `model.` (including the delimiter `.`).

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

In this example, `ext` is defined in `vrfile` as a [token test](docs/VRTokenTests.md) using the `:` syntax, and is referred 
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



