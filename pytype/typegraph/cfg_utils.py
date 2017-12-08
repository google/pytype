"""Utilities for working with the CFG."""

import itertools

import pytype.debug


def MergeVariables(program, node, variables):
  """Create a combined Variable for a list of variables.

  The purpose of this function is to create a final result variable for
  functions that return a list of "temporary" variables. (E.g. function
  calls).

  Args:
    program: A cfg.Program instance.
    node: The current CFG node.
    variables: A list of cfg.Variables.
  Returns:
    A cfg.Variable.
  """
  if not variables:
    return program.NewVariable()  # return empty var
  elif len(variables) == 1:
    v, = variables
    return v
  elif all(v is variables[0] for v in variables):
    return variables[0]
  else:
    v = program.NewVariable()
    for r in variables:
      v.PasteVariable(r, node)
    return v


def MergeBindings(program, node, bindings):
  """Create a combined Variable for a list of bindings.

  Args:
    program: A cfg.Program instance.
    node: The current CFG node.
    bindings: A list of cfg.Bindings.
  Returns:
    A cfg.Variable.
  """
  v = program.NewVariable()
  for b in bindings:
    v.PasteBinding(b, node)
  return v


def CFGAsciiTree(root, forward=False):
  """Draws an ascii tree, starting at the given node.

  Args:
    root: The CFGNode to draw the tree from.
    forward: If True, draw the tree starting at this node. If False, draw
      the "reverse" tree that starts at the current node when following all
      edges in the reverse direction.
      The default is False, because during CFG construction, the current node
      typically doesn't have any outgoing nodes.
  Returns:
    A string.
  """
  if forward:
    return pytype.debug.ascii_tree(root, lambda node: node.outgoing)
  else:
    return pytype.debug.ascii_tree(root, lambda node: node.incoming)


def PrintBinding(binding, indent_level=0):
  """Return a string representation of the (nested) binding contents."""
  return pytype.debug.prettyprint_binding_nested(binding, indent_level)


def WalkBinding(binding, keep_binding=lambda _: True):
  """Helper function to walk a binding's origins.

  Args:
    binding: A cfg.Binding.
    keep_binding: Optionally, a function, cfg.Binding -> bool, specifying
      whether to keep each binding found.

  Yields:
    A cfg.Origin. The caller must send the origin back into the generator. To
    stop exploring the origin, send None back.
  """
  bindings = [binding]
  seen = set()
  while bindings:
    b = bindings.pop(0)
    if b in seen or not keep_binding(b):
      continue
    seen.add(b)
    for o in b.origins:
      o = yield o
      if o:
        bindings.extend(itertools.chain(*o.source_sets))


def CopyVarApprox(program, old_node_range, new_node, old_var):
  """'Copy' the variable from a set of nodes to a single node. An approximation.

  Used to copy origins from a cached return value. Bindings that occur at any
  of the nodes in the cached call are moved to the new node, and all other
  bindings are (approximately) preserved.  See cfg_utils_test for examples.

  Args:
    program: A cfg.Program.
    old_node_range: A slice from the id of the first cfg node in the cached
      call to the id of the last. Create such a slice with
        slice(first_node.id, last_node.id)
      Note that we assume that a node is in the cached call iff its id is
      between these two, inclusive.
    new_node: The cfg node of the current call.
    old_var: A cfg.Variable.

  Returns:
    A cfg.Variable.
  """
  new_var = program.NewVariable()
  for binding in old_var.bindings:
    origins = []
    walker = WalkBinding(binding)
    o = None
    while True:
      try:
        o = walker.send(o)
      except StopIteration:
        break
      if o.where.id < old_node_range.start or old_node_range.stop < o.where.id:
        # This origin is from outside the cached call, so keep it. Send None to
        # the walker so it doesn't go into the origin's source sets.
        o = origins.append(o)
      elif any(not(source_set) for source_set in o.source_sets):
        # The binding has an origin inside the cached call. Since we're
        # copying the entire call onto a single node, we now know that the
        # copied binding should be visible at the new node.
        origins = []
        break
    # Add all of the origins from outside the cached call to the new binding.
    # Loses some of the cached structure because we're adding all of the
    # origins to the same binding but has the advantage of being fast. We also
    # don't preserve the binding data, which doesn't matter since we're
    # creating a new variable.
    origin_var = program.NewVariable()
    for o in origins:
      for source_set in o.source_sets:
        origin_var.AddBinding(binding.data, source_set, o.where)
    new_var.AddBinding(binding.data, origin_var.bindings, new_node)
  return new_var
