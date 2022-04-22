# Valet Rules Usage

## Background

This document provides a basic overview of the usage of Valet Rules.
Its intent is to provide enough context for the new user to get
meaningful output from the system.  Most of the value of Valet Rules
lies in the wide range of patterns that can be authored and
corresponding extractors implemented.  As the authoring of these
patterns does not require Python programming, coverage of the Python 
API internals is limited to to a few API elements.

This document covers four topics: a basic script for driving Valet
Rules from the command line, a step-through of the key lines in the
script, a terminal-based interface to Valet Rules, and a graphical 
user interface to Valet Rules.

The primary Valet Rules tool is the GUI. The script and walkthrough 
are most relevant if you plan to use the Valet Rules [API](VRAPI.md). 
The GUI has mostly replaced the console tool, but the latter may 
still be useful, and also provides more examples of using the API.
There are additional useful scripts, in the `scripts/` directory 
of the installation, that are not documented here.

## Contents

* [Command-line script](VRScript.md) (`scripts/vrcl.py`)
* [Script walkthrough](VRScriptWalkthrough.md)
* [Valet Rules console](VRConsole.md) (`scripts/vrconsole.py`)
* [Valet Rules GUI](VRGui.md) (`scripts/vrgui.py`)

