# Valet Rules

Valet Rules is a flexible framework for implementing efficient
finite-state information extraction from text.

Using Valet Rules, a knowledgeable user can quickly stand up
relatively sophisticated extraction capabilities that exploit a
variety of linguistic features, including orthographic, lexical, and
syntactic. Valet Rules is most appropriate for settings in which
annotated data is lacking or available in insufficient quantities to
train effective machine learning extractors.  It is easiest to use in
cases where a human reader can point to a small number of dominant
expression motifs for the targeted information.

The core of Valet Rules is a text matching rule language that provides 
the following kinds of statement:
* **Import** statements allow you to put rule statements into multiple files 
  and reference one file from another.
* **Phrase** statements define regular expressions over input text tokens.
* **Parse** statements define regular expressions over input text 
  dependency tree edge labels.
* **Token test** statements define how phrase and parse statement regular 
  expressions match individual tokens or edge labels.
* **Coordinator** statements provide various important additional kinds 
  of functionality.
* **Frame** statements enable pulling together information into 
  a key-value "dictionary".

## Documentation

For installation, see [`README.md`](../README.md) in the project root directory.

For all other documentation, including usage, rule language syntax and 
terminology, programming API, and planned enhancements, see the
pages linked below, which may be found in the same directory as this
file.

NOTE: The first three sections under "Usage" below refer to legacy tools 
that are not completely up to date and may not presently work without 
modification. 
(There are some additional, as yet undocumented, scripts that are up to date.)
The Valet Rules GUI is now typically used almost exclusively instead of 
the old Console script.
Many of the planned enhancements mentioned below have already been implemented.

* [Usage](VRUsage.md)
  * [Command-line script](VRScript.md)
  * [Script walkthrough](VRScriptWalkthrough.md)
  * [Console](VRConsole.md)
  * [GUI](VRGui.md)
* [Rule Syntax](VRSyntax.md)
  * [Import Statements](VRImports.md)
  * [Token Tests](VRTokenTests.md)
  * [Phrase Expressions](VRPhraseExpressions.md)
  * [Parse Expressions](VRParseExpressions.md)
  * [Coordinator Expressions](VRCoordinators.md)
  * [Frame Expressions](VRFrames.md)
  * [Bindings](VRBinding.md)
* [API](VRAPI.md)
  * [`TokenSequence`](VRTokenSequence.md)
  * [`FAMatch`](VRMatch.md)
* [Planned Enhancements](VREP.md)
