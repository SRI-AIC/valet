# Token Tests

Statements of the form `<name> : <expression>` define *token tests*,
extractors that operate at the level of individual tokens.  Each such
expression has the effect of essentially defining an equivalence class
of tokens.  The following types of tests are supported:

|Test|Example|Description|
|----|-------|-----------|
|**Regular Expression**|`capitalized : /^[A-Z]/`|tests for starting with capital letters A through Z|
|**Membership**|`article : { a an the }`|tests for membership in a set|
|**Substring**|`occur : <occur>`|tests for an occurrence of a string|
|**Lookup**|`noun : pos[ NN NNS ]`|looks up tags in indicated annotation, here parts of speech|

<!-- ```
# A regular expression test
capitalized : /^[A-Z]/
```
```
# Membership test
article : { a an the }
```
```
# Substring test
occur : <occur>
```
```
# Lookup test
noun : pos[ NN NNS ]
``` -->

<!-- We briefly describe each of these tests in turn and explain how they -->
<!-- can be combined in powerful Boolean expressions. --> 
Below, these tests are briefly described, with explanations of how they can be combined in powerful Boolean expressions.

## Regular Expression Tests

This test return true for any token matching the regular expression it
specifies.  For this purpose, it uses the regular expression syntax
defined in the python `re` module.  A trailing `i` qualifier causes
the test to be applied in a case-insensitive manner.

The characters `^` and `$` are especially useful in regular expressions. 
`^` matches the start of the token, and `$` matches the end of the token. 
So `/hell/` would match `hell` or `hello` or `shell` or `shellfish` or any other token containing `hell`, 
while `/^hell/` would match `hell` or `hello` or any other token starting with `hell`,
and `/hell$/` would match `hell` or `shell` or any other token ending with `hell`.

## Membership Tests

This test returns true for any token found in the membership list,
which is created by splitting the string in between the curly braces
on whitespace.  A trailing `i` qualifier causes the test to be applied
in a case-insensitive manner.

### Membership Test Files (Token Lexicons)

We sometimes use the term "lexicon" to refer to a specific set of literal 
tokens (a token lexicon) or token sequences (a phrase lexicon), typically 
stored in a dedicated file. 

There is variation of membership test syntax that is used for token lexicon 
files. For example, the following rule would be equivalent to the rule above 

```
# Membership test lexicon
article : f{article.txt}
```

if the file `article.txt` contains the tokens `a`, `an`, and `the` 
on separate lines. As with regular membership test rules, a trailing 
`i` qualifier causes the test to be applied in a case-insensitive manner.

Token lexicon files are looked for in the file system according to 
the same rules as [import files](VRImports.md).

## Substring Tests

This test returns true for any token containing the indicated string
as a substring.  A trailing `i` qualifer causes the test to be applied
in a case-insensitive manner.

## Lookup Tests

This test retrieves annotations attached to the raw token sequence,
such as are typically provided by general-purpose NLP components, and
test true for any token having the indicated annotations.  These
annotations are associated with the raw token sequence in a process
that is out of scope for this document.  The number and names of these
annotations are arbitrary.

Interpretation of this kind of test is similar to that used for
membership tests above, except instead of the literal token being
tested for membership, the indicated annotation is tested.  For
example, the expression `pos[ NN NNS ]` specifies that the tag found
in the `pos` layer should be tested for membership in the set `{ NN
NNS }`.  If the `pos` layer stores part-of-speech tags assigned by a
3rd-party module, this would have the effect of selecting nouns.

## References

Any token test may be referenced by the definition of another token
test by prefixing its name with `&`.  For example:

```
noun2 : &noun
myext : &model.ext
```

The above two definitions have the effect of defining new tests that
are equivalent to the test they reference.  (See [Import Statements](./VRImports.md) for the meaning of the `.` syntax.) Note that because the
references are evaluated at runtime, the referenced test need not be
defined before the referencing test is defined.  This ability to
reference is useful in the context of Boolean expressions and 
[phrase expressions](./VRPhraseExpressions.md).

Historically, the `&` prefix was required for references to token tests, 
while a `@` prefix was required for references to phrase expressions 
and parse expresssions. However, the two prefixes may now be used 
interchangeably.

## Boolean Combinations

Any of the test types presented above may be combined in Boolean
expressions using the operators `not`, `and`, and `or`, which have the
usual interpretation and precedence.  In addition, subexpressions may
be nested in parentheses for clarity or to override standard
precedence.  For example:

```
bool : /\d/ or ( &noun and ( &occur or &model.ext ) )
```

This expression is too convoluted and nonsensical to explain in
English, but you get the picture.

## Quoting/Escaping

Note that certain characters or tokens have special meaning in token test expressions and are not interpreted literally. For example, what if you wanted to define a token test for `/` (normally indicates the start of a regex token test) or for `{` (normally indicates the start of a membership test)?

One way to do so is to use a different kind of token test than the one that the character has a special significance in. For example,

```
lbrace : /^{$/
rbrace : /^}$/
fslash : { / }
bslash : { \ }
```

