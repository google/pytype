"""Output utilities for xref."""

from __future__ import print_function

import json


def format_loc(location):
  # location is (line, column)
  fmt = "%d:%d" % location
  return fmt.rjust(8)


def format_def_with_location(defn, loc):
  return ("%s  | %s %s" % (
      format_loc(loc), defn.typ.ljust(15), defn.format()))


def format_ref(ref):
  return ("%s  | %s  %s.%s" % (
      format_loc(ref.location), ref.typ.ljust(15), ref.scope, ref.name))


def typename(node):
  return node.__class__.__name__


def show_defs(index):
  for def_id in index.locs:
    defn = index.defs[def_id]
    for loc in index.locs[def_id]:
      print(format_def_with_location(defn, loc.location))
      if defn.doc:
        print(" "*28 + str(defn.doc))


def show_refs(index):
  for ref, defn in index.links:
    print(format_ref(ref))
    if defn:
      print("          :  ", defn.format())
    else:
      print("          :   None")
    continue


def output_kythe_graph(index):
  for def_id in index.locs:
    defn = index.defs[def_id]
    print(json.dumps(defn.to_vname()._asdict()))

  for x in index.kythe:
    print(json.dumps(x._asdict()))

