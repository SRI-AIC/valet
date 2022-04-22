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

## Documentation

For installation, see [`README.md`](README.md) in the project root directory.

For all other documentation, including usage, terminology, rule
language syntax, programming API, and planned enhancements, see the
pages linked below, which may be found in the same directory as this
file.

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
* [API](VRAPI.md)
  * [`TokenSequence`](VRTokenSequence.md)
  * [`FAMatch`](VRMatch.md)
  * [`Frame`](Frame.md)
* [Planned Enhancements](VREP.md)
