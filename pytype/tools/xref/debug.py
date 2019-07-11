"""Debug utils for working with the indexer and the AST."""

from __future__ import print_function

# pylint: disable=protected-access
# We never care about protected access when writing debug code!


def format_loc(location):
  # location is (line, column)
  fmt = "%d:%d" % location
  return fmt.rjust(8)


def format_def_with_location(defn, loc):
  return ("%s  | %s %s" % (
      format_loc(loc), defn.typ.ljust(15), defn.format()))


def format_ref(ref, keep_pytype_data=False):
  suffix = " : %s" % (ref.data,) if keep_pytype_data else ""
  return ("%s  | %s  %s.%s%s" % (format_loc(
      ref.location), ref.typ.ljust(15), ref.scope, ref.name, suffix))


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


def show_refs(index, keep_pytype_data=False):
  """Show references and associated definitions."""
  indent = "          :  "
  for ref, defn in index.links:
    print(format_ref(ref, keep_pytype_data))
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


def show_index(index, keep_pytype_data=False):
  """Display output in human-readable format."""

  def separator():
    print("\n--------------------\n")

  show_defs(index)
  separator()
  show_refs(index, keep_pytype_data)
  separator()
  show_calls(index)
  separator()


def show_map(name, mapping):
  print("%s: {" % name)
  for k, v in mapping.items():
    print("  ", k, v)
  print("}")


# AST display


def dump(node, ast, annotate_fields=True,
         include_attributes=True, indent="  "):
  """Return a formatted dump of the tree in *node*.

  This is mainly useful for debugging purposes.  The returned string will show
  the names and the values for fields.  This makes the code impossible to
  evaluate, so if evaluation is wanted *annotate_fields* must be set to False.
  Attributes such as line numbers and column offsets are dumped by default. If
  this is not wanted, *include_attributes* can be set to False.

  Arguments:
    node: Top AST node.
    ast: An module providing an AST class hierarchy.
    annotate_fields: Show field annotations.
    include_attributes: Show all attributes.
    indent: Indentation string.

  Returns:
    A formatted tree.
  """
  # Code copied from:
  # http://alexleone.blogspot.com/2010/01/python-ast-pretty-printer.html

  def _format(node, level=0):
    """Format a subtree."""

    if isinstance(node, ast.AST):
      fields = [(a, _format(b, level)) for a, b in ast.iter_fields(node)]
      if include_attributes and node._attributes:
        fields.extend([(a, _format(getattr(node, a), level))
                       for a in node._attributes])
      return "".join([
          node.__class__.__name__,
          "(",
          ", ".join(("%s=%s" % field for field in fields)
                    if annotate_fields else
                    (b for a, b in fields)),
          ")"])
    elif isinstance(node, list):
      lines = ["["]
      lines.extend((indent * (level + 2) + _format(x, level + 2) + ","
                    for x in node))
      if len(lines) > 1:
        lines.append(indent * (level + 1) + "]")
      else:
        lines[-1] += "]"
      return "\n".join(lines)
    return repr(node)

  if not isinstance(node, ast.AST):
    raise TypeError("expected AST, got %r" % node.__class__.__name__)
  return _format(node)
