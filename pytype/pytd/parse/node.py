"""Extension of collections.namedtuple for use in representing immutable trees.

Example usage:

  class Data(Node("d1", "d2", "d3")):
    pass
  class X(Node("a", "b")):
    pass
  class Y(Node("c", "d")):
    pass
  class XY(Node("x", "y")):
    pass
  data = Data(42, 43, 44)
  x = X(1, [1, 2])
  y = Y([1], {"data": data})
  xy = XY(x, y)

  class Visitor:
    def X(self):
      count_x += 1
    def VisitData(self, node):
      return node.Replace(d3=1000)

  new_xy = xy.Visit(Visitor())

The Node "class" differs from namedtuple in the following ways:

1.) More stringent equality test. collections.namedtuple.__eq__ is implicitly
    tuple equality (which makes two tuples equal if all their values are
    recursively equal), but that allows two objects to be the same if they
    happen to have the same field values.
    To avoid this problem, Node adds the check that the two objects' classes are
    equal (this might be too strong, in which case you'd need to use isinstance
    checks).
2.) Visitor interface. See documentation of Visit() below.
3.) Subclassed __str__ function that uses the current class name instead of
    the name of the tuple this class is based on.

If a subclass chooses to use a __dict__ the default equality will only apply
to the class attributes defined as Node args. Therefore
pytd.ClassType("foo", 1) == pytd.ClassType("foo", 2) will compare true.

See http://bugs.python.org/issue16279 for why it is unlikely for any these
functionalities to be made part of collections.namedtuple.
"""

import collections

from pytype import metrics
from pytype.pytd.parse import preconditions


_CHECK_PRECONDITIONS = None


def SetCheckPreconditions(enabled):
  global _CHECK_PRECONDITIONS
  _CHECK_PRECONDITIONS = enabled


def Node(*child_names):
  """Create a new Node class.

  You will typically use this when declaring a new class.
  For example:
    class Coordinate(Node("x", "y")):
      pass

  Arguments:
    *child_names: Names of the children of this node.

  Returns:
    A subclass of (named)tuple.
  """

  precondition_pairs = [preconditions.parse_arg(x) for x in child_names]
  namedtuple_type = collections.namedtuple(
      "_", (p[0] for p in precondition_pairs))
  assert "__init__" not in namedtuple_type.__dict__  # see below

  class NamedTupleNode(namedtuple_type):
    """A Node class based on namedtuple."""

    __slots__ = ()

    _CHECKER = preconditions.CallChecker(precondition_pairs)

    def __init__(self, *args, **kwargs):
      if _CHECK_PRECONDITIONS:
        self._CHECKER.check(*args, **kwargs)
      # We do *not* call super() here, for performance reasons. Neither
      # namedtuple (our base class) nor tuple (namedtuple's base class) do
      # anything in __init__, so it's safe to leave it out.

    def Validate(self):
      """Re-run precondition checks on the node's data."""
      self._CHECKER.check(*self)

    def __eq__(self, other):
      """Compare two nodes for equality.

      This will return True if the two underlying tuples are the same *and* the
      two node types match.

      Arguments:
        other: The Node to compare this one with.
      Returns:
        True or False.
      """
      # This comparison blows up if "other" is an old-style class (not an
      # instance). That's fine, because trying to compare a tuple to a class is
      # almost certainly a programming error, and blowing up is better than
      # silently returning False.
      if self is other:
        return True
      elif self.__class__ is other.__class__:
        return tuple.__eq__(self, other)
      else:
        return False  # or NotImplemented

    def __hash__(self):
      """Return a hash of the node type and the underlying tuple."""
      return hash((self.__class__.__name__,) + self)

    def __ne__(self, other):
      """Compare two nodes for inequality. See __eq__."""
      return not self == other

    def __lt__(self, other):
      """Smaller than other node? Define so we can to deterministic ordering."""
      if self is other:
        return False
      elif self.__class__ is other.__class__:
        return tuple.__lt__(self, other)
      else:
        return self.__class__.__name__ < other.__class__.__name__

    def __gt__(self, other):
      """Larger than other node? Define so we can to deterministic ordering."""
      if self is other:
        return False
      elif self.__class__ is other.__class__:
        return tuple.__gt__(self, other)
      else:
        return self.__class__.__name__ > other.__class__.__name__

    def __le__(self, other):
      return self == other or self < other

    def __ge__(self, other):
      return self == other or self > other

    def __repr__(self):
      """Returns this tuple converted to a string.

      We output this as <classname>(values...). This differs from raw tuple
      output in that we use the class name, not the name of the tuple this
      class extends. Also, Nodes with only one child will be output as
      Name(value), not Name(value,) to match the constructor syntax.

      Returns:
        Representation of this tuple as a string, including the class name.
      """
      if len(self) == 1:
        return "%s(%r)" % (self.__class__.__name__, self[0])
      else:
        return "%s%r" % (self.__class__.__name__, tuple(self))

    # Expose namedtuple._replace as "Replace", so avoid lint warnings
    # and have consistent method names.
    Replace = namedtuple_type._replace  # pylint: disable=no-member,invalid-name

    def Visit(self, visitor, *args, **kwargs):
      """Visitor interface for transforming a tree of nodes to a new tree.

      You can pass a visitor, and callback functions on that visitor will be
      called for all nodes in the tree. Note that nodes are also allowed to
      be stored in lists and as the values of dictionaries, as long as these
      lists/dictionaries are stored in the named fields of the Node class.
      It's possible to overload the Visit function on Nodes, to do your own
      processing.

      Arguments:
        visitor: An instance of a visitor for this tree. For every node type you
          want to transform, this visitor implements a "Visit<Classname>"
          function named after the class of the node this function should
          target. Note that <Classname> is the *actual* class of the node, so
          if you subclass a Node class, visitors for the superclasses will *not*
          be triggered anymore. Also, visitor callbacks are only triggered
          for subclasses of Node.
        *args: Passed to the visitor callback.
        **kwargs: Passed to the visitor callback.

      Returns:
        Transformed version of this node.
      """
      return _Visit(self, visitor, *args, **kwargs)

  return NamedTupleNode


def _CreateUnchecked(cls, *args):
  """Create a node without checking preconditions."""
  global _CHECK_PRECONDITIONS
  old = _CHECK_PRECONDITIONS
  _CHECK_PRECONDITIONS = False
  try:
    return cls(*args)
  finally:
    _CHECK_PRECONDITIONS = old


# The set of visitor names currently being processed.
_visiting = set()


def _Visit(node, visitor, *args, **kwargs):
  """Visit the node."""
  name = type(visitor).__name__
  recursive = name in _visiting
  _visiting.add(name)

  start = metrics.get_cpu_clock()
  try:
    return _VisitNode(node, visitor, *args, **kwargs)
  finally:
    if not recursive:
      _visiting.remove(name)
      elapsed = metrics.get_cpu_clock() - start
      metrics.get_metric("visit_" + name, metrics.Distribution).add(elapsed)
      if _visiting:
        metrics.get_metric(
            "visit_nested_" + name, metrics.Distribution).add(elapsed)


def _VisitNode(node, visitor, *args, **kwargs):
  """Transform a node and all its children using a visitor.

  This will iterate over all children of this node, and also process certain
  things that are not nodes. The latter are either tuples, which will be
  scanned for nodes regardless, or primitive types, which will be return as-is.

  Args:
    node: The node to transform. Either an actual "instance" of Node, or a
          tuple found while scanning a node tree, or any other type (which will
          be returned unmodified).
    visitor: The visitor to apply. If this visitor has a "Visit<Name>" method,
          with <Name> the name of the Node class, a callback will be triggered,
          and the transformed version of this node will be whatever the callback
          returned.  Before calling the Visit callback, the following
          attribute(s) on the Visitor class will be populated:
            visitor.old_node: The node before the child nodes were visited.

          Additionally, if the visitor has a "Enter<Name>" method, that method
          will be called on the original node before descending into it. If
          "Enter<Name>" returns False, the visitor will not visit children of
          this node (the result of "Enter<Name>" is otherwise unused; in
          particular it's OK to return None, which will be ignored).
          ["Enter<Name>" is called pre-order; "Visit<Name> and "Leave<Name>" are
          called post-order.]  A counterpart to "Enter<Name>" is "Leave<Name>",
          which is intended for any clean-up that "Enter<Name>" needs (other
          than that, it's redundant, and could be combined with "Visit<Name>").
    *args: Passed to visitor callbacks.
    **kwargs: Passed to visitor callbacks.
  Returns:
    The transformed Node (which *may* be the original node but could be a new
     node, even if the contents are the same).
  """
  node_class = node.__class__
  if node_class is tuple:
    # Exact comparison for tuple, because classes deriving from tuple
    # (like namedtuple) have different constructor arguments.
    changed = False
    new_children = []
    for child in node:
      new_child = _VisitNode(child, visitor, *args, **kwargs)
      if new_child is not child:
        changed = True
      new_children.append(new_child)
    if changed:
      # Since some of our children changed, instantiate a new node.
      return node_class(new_children)
    else:
      # Optimization: if we didn't change any of the children, keep the entire
      # object the same.
      return node
  elif not isinstance(node, tuple):
    return node

  # At this point, assume node is a Node, which is a namedtuple.
  node_class_name = node_class.__name__
  if node_class_name not in visitor.visit_class_names:
    return node

  if node_class_name in visitor.enter_functions:
    # The visitor wants to be informed that we're descending into this part
    # of the tree.
    status = visitor.Enter(node, *args, **kwargs)
    # Don't descend if Enter<Node> explicitly returns False, but not None,
    # since None is the default return of Python functions.
    if status is False:  # pylint: disable=g-bool-id-comparison
      return node
    # Any other value returned from Enter is ignored, so check:
    assert status is None, repr((node_class_name, status))

  changed = False
  new_children = []
  for child in node:
    new_child = _VisitNode(child, visitor, *args, **kwargs)
    if new_child is not child:
      changed = True
    new_children.append(new_child)
  if changed:
    # The constructor of namedtuple() differs from tuple(), so we have to
    # pass the current tuple using "*".
    if node_class_name in visitor.unchecked_node_names:
      new_node = _CreateUnchecked(node_class, *new_children)
    else:
      new_node = node_class(*new_children)
  else:
    new_node = node

  visitor.old_node = node
  # Now call the user supplied callback(s), if they exist.
  if (visitor.visits_all_node_types or
      node_class_name in visitor.visit_functions):
    new_node = visitor.Visit(new_node, *args, **kwargs)
  if node_class_name in visitor.leave_functions:
    visitor.Leave(node, *args, **kwargs)

  del visitor.old_node
  return new_node
