import re
import sys

"""
Reads the output of print_dependency_trees.py from stdin, 
extracts the dependency edge label, writes it to stdout.
Designed for piping to "sort | uniq -c | sort -n -r -k1,1" 
to count the edges.
Example input (partial):
- Need VB ROOT
  - stopwording NN dobj
    - better JJR amod
"""

for line in sys.stdin:
    matches = list(re.finditer(r"[^ ]+", line.rstrip("\n")))
    if len(matches) == 4 and matches[0].group(0) == "-":
        print(matches[3].group(0))
