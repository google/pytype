"""Debug utils for working with the indexer and the AST."""

from pytype.ast import debug

# pylint: disable=protected-access
# We never care about protected access when writing debug code!


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


def show_defs(index):
  """Show definitions."""
  for def_id in index.locs:
    defn = index.defs[def_id]
    for loc in index.locs[def_id]:
      print(format_def_with_location(defn, loc.location))
      if defn.doc:
        print(" "*28 + str(defn.doc))


def show_refs(index):
  """Show references and associated definitions."""
  indent = "          :  "
  for ref, defn in index.links:
    print(format_ref(ref))
    if defn:
      print(indent, defn.format())
      for loc in index.locs[defn.id]:
        print(indent, format_def_with_location(defn, loc.location))
    else:
      print(indent, "None")
    continue


def show_calls(index):
  for call in index.calls:
    print(format_call(call))


def show_index(index):
  """Display output in human-readable format."""

  def separator():
    print("\n--------------------\n")

  show_defs(index)
  separator()
  show_refs(index)
  separator()
  show_calls(index)
  separator()


def show_map(name, mapping):
  print("%s: {" % name)
  for k, v in mapping.items():
    print("  ", k, v)
  print("}")


# reexport AST dumper

dump = debug.dump
