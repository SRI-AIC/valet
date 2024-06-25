# The Valet Rule Console

## Overview

Valet Rules includes a terminal-based interactive console with which it is more convenient to interact with Valet Rules than with a command-line script.  The console can be accessed via the script
`runvrconsole.py`, with the following usage:

```python
runvrconsole.py [-h] [-s SOURCE_FILE] [-t TARGET_FILE]
```

Options for `runvrconsole.py` are as follow:

|Option|Long Option|Placeholder|Values|Description|
|------|-----------|-----------|------|-----------|
|`-h`|`--help`|||Print a help message and exit|
|`-s`|`--source-file`|`SOURCE_FILE`|(file name)|Input file with pattern definitions|
|`-t`|`--target-file`|`TARGET_FILE`|(file name)|Output file with text|

The name of a source file with pattern definitions is provided as input, and the name of a target file is provided for text output. 

Below, the usage of this script is illustrated with a simple example
involving a search for various monetary expressions in a snippet of
text from a quarterly SEC filing.   

Here is the pattern-definition input in the source file:

```
# Token tests.  

dollar   : { $ }
point    : { . }
leadd   : /^\d\d?\d?$/
twod    : /^\d\d$/

# Phrase patterns.  Numbers and punctuation get separated under the
# default tokenization, so bignum reassembles numbers with
# internal punctuation.

bignum -> &leadd ( , &threed )* ( &point &twod ) ?
money  -> &dollar @bignum
annual -> annual

mamt   ~ select(bignum, match(money, _))
amamt ~ select(bignum, near(annual, 5, 1, match(money, _)))
```
Here is the text output in the target file:

```
On August 11, 2015 (Effective Date), we entered into an exclusive license
agreement (ACL License) with Accelerating Combination Therapies LLC (ACL)
in regards to the exclusive licensing of the issued U.S. Patent No. 8,895,597
B2 Combination of Local Temozolomide with Local BCNU (Patent Rights). Under
the ACL License, we paid ACL a license issue fee of 1,000,000 shares of our
Companys common stock on February 8, 2016. The 1,000,000 shares of common
stock are valued at $1.13 per share, equal to the publicly traded share price
on the Effective Date, are capitalized in the amount of $1,130,000 and
amortized over an expected patent life of 15 years.

On August 11, 2015 ("Effective Date"), the Company entered into an exclusive
license agreement ("ACL License") with Accelerating Combination Therapies LLC
("ACL") in regards to the exclusive licensing of the issued
U.S. Patent No. 8,895,597 B2 _Combination of Local Temozolomide with Local BCNU_ ( "Patent
Rights"). Under the ACL License, the Company paid ACL a license issue fee of
1,000,000 shares of our Company's common stock on February 8, 2016. The
1,000,000 shares of common stock are valued at $1.13 per share, equal to the
publicly traded share price on the Effective Date, are capitalized in the
amount of $1,130,000 and amortized over an expected patent life of 15 years.
The gross carrying amount was $1,025,393, accumulated amortization was
$104,607 and quarterly amortization expense was $18,833 as of December 31,
2016. The gross carrying amount was $1,100,726, accumulated amortization was
$29,274 and quarterly amortization expense was $18,833 as of December 31,
2015.
```

When the console is accessed, the following command prompt is displayed:

```
Valet Rules command console.  Type help or ? for a command list

:: 
```

The user interacts with the console by entering commands at the `::` prompt,
usually with an argument.  The console has readline support, so it's
possible to scroll up and down the list of previously executed
commands with the up and down arrows.  The console also has command-line completion, which is provided
for most commands, and can be invoked via the tab key.

The console is rough and ready.  By design, the prompt stays at the
top of the terminal, and each successive command clears and
repopulates the rest of the screen.  Internal error conditions (e.g.
caused by providing the name of a non-existent file to a command that expects a file) may cause this design to fail, but it's usually possible to recover by executing a command that the console is able to
process.

## Console Commands

The console understands the following commands:

|Command|Action|
|-------|------|
|[`source`](#source-command)|Interpret a new source file.|
|[`target`](#target-command)|Adopt a new text file as target.|
|[`def`](#def-command)|Execute a Valet Rules statement directly.|
|[`extract`](#extract-command)|Execute a pattern and display matching strings.|
|[`mark`](#mark-command)|Execute a pattern and show matches in context.|
|[`set`](#set-command)|Set configuration variables.|
|[`show`](#show-command)|Show pattern definitions.|
|[`help`](#help-command)|Retrieve help.|

### Source Command

**Usage**

```
source <filename>
```

The `source` command reads and evaluates the statements in the specified file.
Any statements that provide an expression for a previously defined
name will overwrite the definition associated with that name.  Because
auto-completion expands to the previously specified source file name
on an empty argument, a useful debugging loop is to tinker with
definitions in the source file, issue the `source` command, then
explore the effect of updated definitions.

### Target Command

**Usage**

```
target <filename>
```

The `target` command sets the file to use as a source of text data.
Typically, this is a plain text file, but it's possible to specify
other kinds of input in ways that are outside the scope of this
documentation.  Subsequent commands that process text will use the
contents of the indicated file.

### Def Command

**Usage**

```
def <statement>
```

The `def` command accepts and processes a single Valet Rules statement as
if it had been included in the source file.

**Example**

```
def direction : { north south east west}i
```

The above statement would define (or redefine) a token test called
"direction" that matches the indicated words in a case-insensitive
fashion.

### Extract Command

**Usage**

```
extract <extractor>
```

The `extract` command applies the indicated extractor, referenced by name, to the
specified text file. All matches are displayed as a list of
strings.  The list is truncated if it would extend off the end of the
screen.

**Example**

```
extract money
```

yields:

```
Matches:  $ 1 . 13
  $ 1 , 130 , 000
  $ 1 . 13
  $ 1 , 130 , 000
  $ 1 , 025 , 393
  $ 104 , 607
  $ 18 , 833
  $ 1 , 100 , 726
  $ 29 , 274
  $ 18 , 833
```

### Mark Command

**Usage**

```
mark <extractor>
```

The `mark` command is similar to the `extract` command, except that it displays the input
file with matches marked by underlines and in red.

**Example**

The command:

```
mark mamt
```

yields:

> On August 11, 2015 (Effective Date), we entered into an exclusive license
> agreement (ACL License) with Accelerating Combination Therapies LLC (ACL)
> in regards to the exclusive licensing of the issued U.S. Patent No. 8,895,597
> B2 Combination of Local Temozolomide with Local BCNU (Patent Rights). Under
> the ACL License, we paid ACL a license issue fee of 1,000,000 shares of our
> Companys common stock on February 8, 2016. The 1,000,000 shares of common
> stock are valued at $**1.13** per share, equal to the publicly traded share price
> on the Effective Date, are capitalized in the amount of $**1,130,000** and
> amortized over an expected patent life of 15 years.
> 
> On August 11, 2015 ("Effective Date"), the Company entered into an exclusive
> license agreement ("ACL License") with Accelerating Combination Therapies LLC
> ("ACL") in regards to the exclusive licensing of the issued
> U.S. Patent No. 8,895,597 B2 _Combination of Local Temozolomide with Local BCNU_ ( "Patent
> Rights"). Under the ACL License, the Company paid ACL a license issue fee of
> 1,000,000 shares of our Company's common stock on February 8, 2016. The
> 1,000,000 shares of common stock are valued at $**1.13** per share, equal to the
> publicly traded share price on the Effective Date, are capitalized in the
> amount of $**1,130,000** and amortized over an expected patent life of 15 years.
> The gross carrying amount was $**1,025,393**, accumulated amortization was
> $**104,607** and quarterly amortization expense was $**18,833** as of December 31,
> 2016. The gross carrying amount was $**1,100,726**, accumulated amortization was
> $**29,274** and quarterly amortization expense was $**18,833** as of December 31,
> 2015.

(Note that the example above uses boldface and Markdown's blockquote, due to generic Markdown's inability to reproduce the styling used by the console.)

### Set Command

**Usage**

```
set <parameter> <value>
```

The `set` command sets the value of a parameter determining the console's behavior.  At the moment,
there is only one such parameter - `maxlines`, which governs how
many vertical lines to display.  Its value should be a positive integer.

### Show Command

**Usage**

```
show <thing>
```

Th `show` command displays some aspect of the execution environment.
Currently, the `<thing>` argument value can be one of `tests`, `patterns`, `coords`, or
`maxlines`.

**Example**

```
show patterns
```

yields

```
annual -> annual
bignum -> &leadd ( , &threed )* ( &point &twod ) ?
money  -> &dollar @bignum
```

### Help Command

**Usage**
```
help
```

or

```
help <command-name>
```

The first call to `help` - without a `<command-name>` argument value  - prints a list of available commands.  The second call to `help` - with a `<command-name>` argument value  - prints a succinct usage message for the named command, which must be one of the commands covered in this file.

