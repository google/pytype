"""Output utilities for xref."""

from __future__ import print_function


def format_loc(location):
  # location is (line, column)
  fmt = "%d:%d" % location
  return fmt.rjust(8)


def format_def_with_location(defn, loc):
  return ("%s  | %s %s" % (
      format_loc(loc), defn.typ.ljust(15), defn.format()))


def format_ref(ref):
  return ("%s  | %s  %s::%s" % (
      format_loc(ref.location), ref.typ.ljust(15), ref.scope, ref.name))


def typename(node):
  return node.__class__.__name__


def show_defs(index):
  for def_id in index.locs:
    for loc in index.locs[def_id]:
      print(format_def_with_location(index.defs[def_id], loc.location))


def show_refs(index):
  for ref, defn in index.links:
    print(format_ref(ref))
    if defn:
      print("          :  ", defn.format())
    else:
      print("          :   None")
    continue


def display_traces(src, traces):
  """Format and print the output of indexer.collect_traces."""

  source = src.split("\n")
  for line in sorted(traces.keys()):
    print("%d %s" % (line, source[line - 1]))
    for name, symbol, data in traces[line]:
      print("  %s : %s <- %s %s" % (
          name, symbol, data, data and [typename(x) for x in data]))
    print("-------------------")
