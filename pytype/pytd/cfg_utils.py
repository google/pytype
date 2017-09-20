"""Utilities for working with the CFG."""

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
