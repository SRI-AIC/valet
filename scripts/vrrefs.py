import re
import sys

from ordered_set import OrderedSet
import plac

from valetrules.manager import VRManager


"""
Shows a tree view of all the rules (pattern names) referenced directly and 
indirectly by the specified rules, or by all rules in the pattern file if none 
are specified.
In the latter case, also lists unreferenced patterns within the pattern file.
"""

# TODO? This does not currently respect substitutions defined in the rules,
# as in tests/test_binding.py.


def main(pattern_file: ("File containing pattern definitions", "positional"),
         patterns: ("Names of the patterns to use (space delimited, empty string for none)", "positional", None, str),
         ):

    vrm = VRManager()
    vrm.parse_file(pattern_file)

    pattern_names = re.findall(r'\S+', patterns)
    if len(pattern_names) == 0:
        pattern_names = all_pattern_names = vrm.all_extractor_names()  # only from top level file
        referenced = OrderedSet()
    else:
        referenced = None  # don't track

    for patname in pattern_names:
        show(vrm, vrm, referenced, patname, 0)

    if referenced is not None:
        unreferenced = OrderedSet(all_pattern_names) - referenced
        print(f"Unreferenced patterns: {list(unreferenced)}")


def show(topmgr, mgr, referenced, patname, indent=0):
    """
    topmgr  - corresponds to the rules file passed to the script
    mgr     - the VRManager to evaluate patname with respect to;
              this could be a submanager that handles an imported file
    patname - can be a qualified name like stx.base_noun_phrase"""

    print(f"{' ' * indent}", end="")
    print(f"{patname}")

    if mgr is topmgr and indent > 0 and referenced is not None:
        # FWIW, since patname could be qualified, if it is we may not
        # really need to add it to referenced, but shouldn't hurt.
        # There might be a smarter way of doing this, though.
        referenced.add(patname)

    # Find the extractor instance for the pattern (rule) name.
    extractor, type_, substitutions = mgr.lookup_extractor(patname)
    # Get the manager that the pattern really belongs to.
    # For a qualified name like stx.base_noun_phrase, this would be the
    # manager for the syntax.vrules file.
    mgr = extractor.manager
    if mgr is not None:
        refnames = extractor.references()  # pattern names referred to by the extractor's pattern
        # TODO? Apply substitutions to each refname?
        for refname in refnames:
            show(topmgr, mgr, referenced, refname, indent + 2)
    # else:
    #     print(f"'{patname}' has no manager")


plac.call(main)
