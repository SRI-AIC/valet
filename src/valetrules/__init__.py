"""
Modules:
coordinator    - implements coordinator expressions
coordinatorexp - parses coordinator expressions
expression     - abstract base class for expressions
extractor      - abstract base class for extractors derived from expressions
fa             - finite automata implementing phrase and parse expressions
frame          - implements frame expressions
macro          - NYI
manager        - holds interrelated set of objects representing set of parsed patterns, performs matching against token sequences
match          - objects representing matches of expressions against token sequences
query          - TBD
regex          - implements token-level regular expressions used in phrase and parse expressions
state          - states of finite automata
statement      - parses statements in the VR pattern language into internal representations
tokentest      - implements token test expressions
transition     - transitions of finite automate
vrconsole      - higher level tool
"""
