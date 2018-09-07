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


def format_call(call):
  return ("%s  | %s  %s" % (
      format_loc(call.location), "Call".ljust(15), call.func))


def typename(node):
  return node.__class__.__name__


def unpack(obj):
  """Recursively expand namedtuples into dicts."""

  if hasattr(obj, "_asdict"):
    return {k: unpack(v) for k, v in obj._asdict().items()}
  elif isinstance(obj, dict):
    return {k: unpack(v) for k, v in obj.items()}
  elif isinstance(obj, list):
    return [unpack(v) for v in obj]
  elif isinstance(obj, tuple):
    return tuple(unpack(v) for v in obj)
  else:
    return obj


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


def show_calls(index):
  for call in index.calls:
    print(format_call(call))


def output_kythe_graph(index):
  for x in index.kythe.entries:
    print(json.dumps(unpack(x)))
