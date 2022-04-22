# Phrase Expressions

Phrase expressions define extractors that operate over token sequences
and return matching subsequences.  A phrase expression is defined with
the following syntax:

```
<name> -> <expression>
```

Literals in the expression (`<token>s`) in the grammar below) can be treated case-insensitively by prefixing 
the `->` delimiter with `i`.

```
<name> i-> <expression>
```

## Expression grammar

The `<expression>` value is written in a regular expression syntax using
the following grammar. (Note that `->` in the grammar is essentially unrelated 
to the literal `->` delimiter in between the `<name>` and `<expression>` 
in the phrase expression statement.)

```
<expression> -> <altern> 
```
```
<altern> -> <concat>
          | <concat> '|' <altern>      # Alternative subexpressions
```
```
<concat> -> <qualified_atom>
          | <qualified_atom> <concat>  # Sequential subexpressions
```
```
<qualified_atom> -> <atom>             # Unqualified (exactly one occurrence)
                  | <atom> '?'         # Optional (zero or one occurrences)
                  | <atom> '+'         # Kleene plus (one or more occurrences)
                  | <atom> '*'         # Kleene star (zero or more occurrences)
```
```
<atom> -> '(' <expression> ')'         # Subexpression
        | <token>
        | <test_reference>
        | <phrase_reference>
```
```
<token>            -> <literal>        # Matches literally
```
```
<test_reference>   -> '&'<identifier>  # Reference to token test
```
```
<phrase_reference> -> '@'<identifier>  # Reference to other phrase expression
```

This defines a more or less standard regular expression syntax, but
is applied to token sequences rather than character sequences.

A 'token' is any string of word characters or single
characters of punctuation that does not have a special meaning in the
grammar.  When encountering such an element, the expression
interpreter treats it as a literal test.  In other words, a particular
token embedded in some token sequence must match it exactly, character
by character, for the element to match.  

An 'identifier' is a sequence of word (\w) characters as defined by 
the Python regular expression module, possibly with embedded '.' characters 
indicating following names from import statements (for example,
[`bar.baz.ext`](docs/VRImports.md)).

As with token test Boolean expressions, subexpressions may be nested 
in parentheses for clarity or to override standard precedence.

Historically, the `&` prefix was required for references to token tests, 
while the `@` prefix was required for references to phrase expressions 
and parse expresssions. However, the two prefixes may now be used 
interchangeably.

## Example

For a concrete example, consider the following statemements:

```
# A number token
num : /^\d+$/
```
```
# A numeric expression, possibly with commas and/or decimal point
bignum -> &num ( , &num ) * ( . &num ) ?
```
```
# A currency recognizer
money -> $ @bignum
```

The `bignum` expression recognizes a certain class of numeric
expressions, including numbers large enough to require internal
punctuation.  (Note that it ignores the typical constraint that
internally delimited digit sequences typically have exactly 3 digits.
We could define a new test and change the definition to make it more
selective.)  The characters `,` and `.` in this expression have no special 
interpretation and are therefore treated as literal tests (in contrast 
to the `(`, `)`, `*`, and `?`, which do have special interpretations).

The `money` expression references the `bignum` expression to implement
an extractor for (US) currency expressions (using a literal test for
`$`).

## Submatch capture

In addition to potentially enhancing the clarity of the model,
this use of named subexpressions enables submatch capture.  The object
created from some match of the `money` expression also tracks where
the internally referenced `bignum` pattern matches.  Thus, if downstream
expressions or code wants the numeric portion of the currency expression,
it can query for the portion that matches `bignum`.  Further documentation
describes how to achieve this elegantly with
[select](VRCoordinators.md#select-operator)
[coordinator](VRCoordinators.md) expressions.

## Predefined phrase identifiers

There are two predefined phrase identifiers, `START` and `END`, which define
zero-width matches at the start and end of a token sequence, respectively.
These serve the same purpose for phrase expressions as the `^` and `$`
characters do for regular expressions, as in the regular expression token test
statement above: `num : /^\d+$/`.
For example, `all_numbers -> @START &num+ @END`.

## Phrase lexicons

Similar to [token lexicons](./VRTokenTests.md), it is possible to define 
lexicons of literal phrases specified in a file. For example, if a file 
`greetings.txt` contains the following text

```
hello
hi there
how's it going
```

then the rule

```
greetings Li-> greetings.txt
```

is equivalent to the rule 

```
greetings i-> hi | hello there | how ' s it going
```

Valet's standard tokenization is applied to each line in the text file 
to determine the individual tokens.

Phrase lexicon files are looked for in the file system according to 
the same rules as [import files](VRImports.md).

## Quoting/Escaping

Note that certain characters or tokens have special meaning in phrase
expressions and are not interpreted literally. For example, what if you
wanted to define a phrase expression that would match phrases like `1 + 2`
or `18 + 35`? Defining `sum -> &num + &num` would not work because of
the special meaning of `+`, which indicates one or more occurrences
of the expression to the left. 

Instead, one could define a [token test](./VRTokenTests.md) `plus : { + }`
and reference it like so: `sum -> &num &plus &num`.
The same technique can be used to quote or escape the other characters 
`*`, `?`, `(`, `)`, `&`, and `@` that have special significance in the 
grammar for phrase expressions.


