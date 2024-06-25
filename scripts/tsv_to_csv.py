#!/usr/bin/env python

import csv
import sys

# Convenience script for converting TSV to CSV,
# e.g., to allow loading into nlpcore.lexicon.Lexicon.
# Could enhance to allow use of stdin/out, etc.

infile = sys.argv[1]
outfile = sys.argv[2]

with open(infile, "r", newline="") as in_fh:
    reader = csv.reader(in_fh, delimiter="\t", quoting=csv.QUOTE_NONE)
    with open(outfile, "w", newline="") as out_fh:
        writer = csv.writer(out_fh, lineterminator="\n")
        for row in reader:
            writer.writerow(row)
