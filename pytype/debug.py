"""Debugging helper functions."""

import logging
import re
import StringIO
import traceback
import utils


def _ascii_tree(io, node, p1, p2, seen, get_children, get_description=None):
  """Draw a graph, starting at a given position.

  Args:
    io: A file-like object to write the ascii tree to.
    node: The node from where to draw.
    p1: The current prefix.
    p2: The upcoming prefix.
    seen: Nodes we have seen so far (as a set).
    get_children: The function to call to retrieve children.
    get_description: Optional. A function to call to describe a node.
  """
  children = list(get_children(node))
  text = get_description(node) if get_description else str(node)
  if node in seen:
    io.write(p1 + "[" + text + "]\n")
  else:
    io.write(p1 + text + "\n")
    seen.add(node)
    for i, c in enumerate(children):
      last = (i == len(children) - 1)
      io.write(p2 + "|\n")
      _ascii_tree(io, c, p2 + "+-", p2 + ("  " if last else "| "),
                  seen, get_children, get_description)


def ascii_tree(node, get_children, get_description=None):
  """Draw a graph, starting at a given position.

  Args:
    node: The node from where to draw.
    get_children: The function to call to retrieve children.
    get_description: Optional. A function to call to describe a node.

  Returns:
    A string.
  """
  io = StringIO.StringIO()
  _ascii_tree(io, node, "", "", set(), get_children, get_description)
  return io.getvalue()


def prettyprint_binding(binding, indent_level=0):
  """Pretty print a binding with variable id and data."""
  indent = " " * indent_level
  if not binding:
    return indent + "<>"
  return "%s<v%d : %r>" % (indent, binding.variable.id, binding.data)


def prettyprint_binding_set(binding_set, indent_level=0, label=""):
  """Pretty print a set of bindings, with optional label."""
  indent = " " * indent_level
  start = "%s%s: {" % (indent, label)
  if not binding_set:
    return start + " }"
  return "\n".join(
      [start] +
      [prettyprint_binding(x, indent_level + 2) for x in binding_set] +
      [indent + "}"])


def prettyprint_binding_nested(binding, indent_level=0):
  """Pretty print a binding and its recursive contents."""
  indent = " " * indent_level
  if indent_level > 32:
    return indent + "-[ max recursion depth exceeded ]-\n"
  s = "%sbinding v%s=%r\n" % (indent, binding.variable.id, binding.data)
  other = ""
  for v in binding.variable.bindings:
    if v is not binding:
      other += "%r %s " % (v.data, [o.where for o in v.origins])
  if other:
    s += "%s(other assignments: %s)\n" % (indent, other)
  for origin in binding.origins:
    s += "%s  at %s\n" % (indent, origin.where)
    for i, source_set in enumerate(origin.source_sets):
      for j, source in enumerate(source_set):
        s += prettyprint_binding_nested(source, indent_level + 4)
        if j < len(source_set)-1:
          s += "%s    AND\n" % indent
      if i < len(origin.source_sets)-1:
        s += "%s  OR\n" % indent
  return s


def _pretty_variable(var):
  """Return a pretty printed string for a Variable."""
  lines = []
  single_value = len(var.bindings) == 1
  var_desc = "v%d" % var.id
  if not single_value:
    # Write a description of the variable (for single value variables this
    # will be written along with the value later on).
    lines.append(var_desc)
    var_prefix = "  "
  else:
    var_prefix = var_desc + " = "

  for value in var.bindings:
    i = 0 if value.data is None else value.data.id
    data = utils.maybe_truncate(value.data)
    binding = "%s#%d %s" % (var_prefix, i, data)

    if len(value.origins) == 1:
      # Single origin.  Use the binding as a prefix when writing the orign.
      prefix = binding + ", "
    else:
      # Multiple origins, write the binding on its own line, then indent all
      # of the origins.
      lines.append(binding)
      prefix = "    "

    for origin in value.origins:
      src = utils.pretty_dnf([[str(v) for v in source_set]
                              for source_set in origin.source_sets])
      lines.append("%s%s @%d" %(prefix, src, origin.where.id))
  return "\n".join(lines)


def program_to_text(program):
  """Generate a text (CFG nodes + assignments) version of a program.

  For debugging only.

  Args:
    program: An instance of cfg.Program

  Returns:
    A string representing all of the data for this program.
  """
  def label(node):
    return "<%d>%s" % (node.id, node.name)
  s = StringIO.StringIO()
  seen = set()
  for node in utils.order_nodes(program.cfg_nodes):
    seen.add(node)
    s.write("%s\n" % label(node))
    s.write("  From: %s\n" % ", ".join(label(n) for n in node.incoming))
    s.write("  To: %s\n" % ", ".join(label(n) for n in node.outgoing))
    s.write("\n")
    variables = set(value.variable for value in node.bindings)
    for var in sorted(variables, key=lambda v: v.id):
      # If a variable is bound in more than one node then it will be listed
      # redundantly multiple times.  One alternative would be to only list the
      # values that occur in the given node, and then also list the other nodes
      # that assign the same variable.

      # Write the variable, indenting by two spaces.
      s.write("  %s\n" % _pretty_variable(var).replace("\n", "\n  "))
    s.write("\n")

  return s.getvalue()


def program_to_dot(program, ignored, only_cfg=False):
  """Convert a cfg.Program into a dot file.

  Args:
    program: The program to convert.
    ignored: A set of names that should be ignored. This affects most kinds of
    nodes.
    only_cfg: If set, only output the control flow graph.
  Returns:
    A str of the dot code.
  """
  def objname(n):
    return n.__class__.__name__ + str(id(n))

  print("cfg nodes=%d, vals=%d, variables=%d" % (
      len(program.cfg_nodes),
      sum(len(v.bindings) for v in program.variables),
      len(program.variables)))

  sb = StringIO.StringIO()
  sb.write("digraph {\n")
  for node in program.cfg_nodes:
    if node in ignored:
      continue
    sb.write("%s[shape=polygon,sides=4,label=\"<%d>%s\"];\n"
             % (objname(node), node.id, node.name))
    for other in node.outgoing:
      sb.write("%s -> %s [penwidth=2.0];\n" % (objname(node), objname(other)))

  if only_cfg:
    sb.write("}\n")
    return sb.getvalue()

  for variable in program.variables:
    if variable.id in ignored:
      continue
    if all(origin.where == program.entrypoint
           for value in variable.bindings
           for origin in value.origins):
      # Ignore "boring" values (a.k.a. constants)
      continue
    sb.write('%s[label="%d",shape=polygon,sides=4,distortion=.1];\n'
             % (objname(variable), variable.id))
    for val in variable.bindings:
      sb.write("%s -> %s [arrowhead=none];\n" %
               (objname(variable), objname(val)))
      sb.write("%s[label=\"%s@0x%x\",fillcolor=%s];\n" %
               (objname(val), repr(val.data)[:10], id(val.data),
                "white" if val.origins else "red"))
      for loc, srcsets in val.origins:
        if loc == program.entrypoint:
          continue
        for srcs in srcsets:
          sb.write("%s[label=\"\"];\n" % (objname(srcs)))
          sb.write("%s -> %s [color=pink,arrowhead=none,weight=40];\n"
                   % (objname(val), objname(srcs)))
          if loc not in ignored:
            sb.write("%s -> %s [style=dotted,arrowhead=none,weight=5]\n"
                     % (objname(loc), objname(srcs)))
          for src in srcs:
            sb.write("%s -> %s [color=lightblue,weight=2];\n"
                     % (objname(src), objname(srcs)))
  sb.write("}\n")
  return sb.getvalue()


def root_cause(binding, node, seen=()):
  """Tries to determine why a binding isn't possible at a node.

  This tries to find the innermost source that's still impossible. It only works
  if the failure isn't due to a combination of bindings. (Use pytd/explain.py
  for the latter)

  Args:
    binding: A binding, or a list of bindings.
    node: The node at which (one of the) binding(s) is impossible.
    seen: Internal. Bindings already looked at.

  Returns:
    A tuple (binding, node), with "binding" the innermost binding that's
    not possible, and "node" the CFG node at which it isn't.
  """
  if isinstance(binding, (list, tuple)):
    bindings = list(binding)
  else:
    bindings = [binding]
  del binding
  key = frozenset(bindings)
  if key in seen:
    return next(iter(bindings), None), node
  for b in bindings:
    if not node.HasCombination([b]):
      for o in b.origins:
        for source_set in o.source_sets:
          cause, n = root_cause(list(source_set), o.where)
          if cause is not None:
            return cause, n
      return b, node
  return None, None


def stack_trace(indent_level=0, limit=100):
  indent = " " * indent_level
  stack = [frame for frame in traceback.extract_stack()
           if "/errors.py" not in frame[0] and "/debug.py" not in frame[0]]
  trace = traceback.format_list(stack[-limit:])
  trace = [indent + re.sub(r"/usr/.*/pytype/", "", x) for x in trace]
  return "\n  ".join(trace)


def patch_logging():
  """Add one extra log level, "TRACE", to logging."""
  def trace(self, msg, *args, **kwargs):
    if self.isEnabledFor(logging.DEBUG - 1):
      # pylint: disable=protected-access
      self._log(logging.DEBUG - 1, msg, args, **kwargs)
  logging.TRACE = logging.DEBUG - 1
  logging.Logger.trace = trace
  logging.addLevelName(logging.DEBUG - 1, "TRACE")


def set_logging_level(level):
  if logging.root.handlers:
    logging.root.setLevel(level)
  else:
    logging.basicConfig(level=level)


patch_logging()
