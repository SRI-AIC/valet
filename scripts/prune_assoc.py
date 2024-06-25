"""Prune an xxAssoc.tsv file, writing to a new file.
(Could be used on certain other Jminer output files too.)
xxAssoc.tsv file is read by nlpcore.term_expansion.
File has three columns: term index, associated term index, divergence value.

Command line argumetns:
infile path
outfile path
limit (default 40) - number of x2 associations to keep for each x1
sort_by_index (default True) - output format is like input format, but pruned

With sort_by_index False, x2's are sorted by divergence instead of index,
so closest associations first.

Jminer details:
A full xxAssoc.tsv file (all xx pairs) is written by jminer.cli.Associations.
This script lets you prune that file."""

import ast
from collections import defaultdict
import sys


infile = sys.argv[1]
outfile = sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
# The input file is normally sorted by index, 
# but it's probably fine if the output file isn't.
sort_by_index = ast.literal_eval(sys.argv[4]) if len(sys.argv) > 4 else True

# Read in data.
with open(infile) as fh:
    data = defaultdict(dict)
    for line in fh:
        fields = line.rstrip("\n").split("\t")
        x1 = int(fields[0])
        x2 = int(fields[1])
        diver = float(fields[2])
        data[x1][x2] = diver

# Prune and write.
# Assuming the x1 x2 values are sorted in the input file, as they should be.
# Assuming a later version of python so dicts preserve insertion order;
# otherwise would need to sort the x1 keys.
with open(outfile, "w") as fh:
    for x1, sub in data.items():
        s = sorted(sub.items(), key=lambda tupl: tupl[1])
        s = s[0:limit]
        if sort_by_index:
            s = sorted(s, key=lambda tupl: tupl[0])
        for x2, diver in s:
            print(f"{x1}\t{x2}\t{diver}", file=fh)
