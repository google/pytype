"""Base class for visitors."""

from typing import Any

from pytype.pytd import pytd
from pytype.typegraph import cfg_utils

# A convenient value for unchecked_node_classnames if a visitor wants to
# use unchecked nodes everywhere.
ALL_NODE_NAMES = type(
    "contains_everything",
    (),
    {"__contains__": lambda *args: True})()


class _NodeClassInfo:
  """Representation of a node class in the precondition graph."""

  def __init__(self, cls):
    self.cls = cls  # The class object.
    self.name = cls.__name__
    # The set of NodeClassInfo objects that may appear below this particular
    # type of node.  Initially empty, filled in by examining preconditions.
    self.outgoing = set()


def _FindNodeClasses():
  """Yields _NodeClassInfo objects for each node found in pytd."""
  for name in dir(pytd):
    value = getattr(pytd, name)
    if isinstance(value, type) and hasattr(value, "_CHECKER"):
      yield _NodeClassInfo(value)


_IGNORED_TYPENAMES = frozenset(["str", "bool", "int", "NoneType"])
_ancestor_map = None  # Memoized ancestors map.


def _GetAncestorMap():
  """Return a map of node class names to a set of ancestor class names."""

  global _ancestor_map
  if _ancestor_map is None:
    # Map from name to _NodeClassInfo.
    node_classes = {i.name: i for i in _FindNodeClasses()}

    # Update _NodeClassInfo.outgoing based on preconditions.
    for info in node_classes.values():
      for allowed in info.cls._CHECKER.allowed_types():  # pylint: disable=protected-access
        if isinstance(allowed, type):
          # All subclasses of the type are allowed.
          info.outgoing.update(
              [i for i in node_classes.values() if issubclass(i.cls, allowed)])
        elif allowed in node_classes:
          info.outgoing.add(node_classes[allowed])
        elif allowed not in _IGNORED_TYPENAMES:
          # This means preconditions list a typename that is unknown.  If it
          # is a node then make sure _FindNodeClasses() can discover it.  If it
          # is not a node, then add the typename to _IGNORED_TYPENAMES.
          raise AssertionError("Unknown precondition typename: %s" % allowed)

    predecessors = cfg_utils.compute_predecessors(node_classes.values())
    # Convert predecessors keys and values to use names instead of info objects.
    get_names = lambda v: {n.name for n in v}
    _ancestor_map = {k.name: get_names(v) for k, v in predecessors.items()}
  return _ancestor_map


class Visitor:
  """Base class for visitors.

  Each class inheriting from visitor SHOULD have a fixed set of methods,
  otherwise it might break the caching in this class.

  Attributes:
    visits_all_node_types: Whether the visitor can visit every node type.
    unchecked_node_names: Contains the names of node classes that are unchecked
      when constructing a new node from visited children.  This is useful
      if a visitor returns data in part or all of its walk that would violate
      node preconditions.
    enter_functions: A dictionary mapping node class names to the
      corresponding Enter functions.
    visit_functions: A dictionary mapping node class names to the
      corresponding Visit functions.
    leave_functions: A dictionary mapping node class names to the
      corresponding Leave functions.
    visit_class_names: A set of node class names that must be visited.  This is
      constructed based on the enter/visit/leave functions and precondition
      data about legal ASTs.  As an optimization, the visitor will only visit
      nodes under which some actionable node can appear.
  """
  # The old_node attribute contains a copy of the node before its children were
  # visited. It has the same type as the node currently being visited.
  old_node: Any

  visits_all_node_types = False
  unchecked_node_names = set()

  _visitor_functions_cache = {}

  def __init__(self):
    cls = self.__class__

    # The set of method names for each visitor implementation is assumed to
    # be fixed. Therefore this introspection can be cached.
    if cls in Visitor._visitor_functions_cache:
      enter_fns, visit_fns, leave_fns, visit_class_names = (
          Visitor._visitor_functions_cache[cls])
    else:
      enter_fns = {}
      enter_prefix = "Enter"
      enter_len = len(enter_prefix)

      visit_fns = {}
      visit_prefix = "Visit"
      visit_len = len(visit_prefix)

      leave_fns = {}
      leave_prefix = "Leave"
      leave_len = len(leave_prefix)

      for attr in dir(cls):
        if attr.startswith(enter_prefix):
          enter_fns[attr[enter_len:]] = getattr(cls, attr)
        elif attr.startswith(visit_prefix):
          visit_fns[attr[visit_len:]] = getattr(cls, attr)
        elif attr.startswith(leave_prefix):
          leave_fns[attr[leave_len:]] = getattr(cls, attr)

      ancestors = _GetAncestorMap()
      visit_class_names = set()
      # A custom Enter/Visit/Leave requires visiting all types of nodes.
      visit_all = (cls.Enter != Visitor.Enter or
                   cls.Visit != Visitor.Visit or
                   cls.Leave != Visitor.Leave)
      for node in set(enter_fns) | set(visit_fns) | set(leave_fns):
        if node in ancestors:
          visit_class_names.update(ancestors[node])
        elif node:
          # Visiting an unknown non-empty node means the visitor has defined
          # behavior on nodes that are unknown to the ancestors list.  To be
          # safe, visit everything.
          #
          # TODO(dbaum): Consider making this an error.  The only wrinkle is
          # that StrictType is unknown to _FindNodeClasses(), does not appear
          # in any preconditions, but has defined behavior in PrintVisitor.
          visit_all = True
      if visit_all:
        visit_class_names = ALL_NODE_NAMES
      Visitor._visitor_functions_cache[cls] = (
          enter_fns, visit_fns, leave_fns, visit_class_names)

    self.enter_functions = enter_fns
    self.visit_functions = visit_fns
    self.leave_functions = leave_fns
    self.visit_class_names = visit_class_names

  def Enter(self, node, *args, **kwargs):
    return self.enter_functions[node.__class__.__name__](
        self, node, *args, **kwargs)

  def Visit(self, node, *args, **kwargs):
    return self.visit_functions[node.__class__.__name__](
        self, node, *args, **kwargs)

  def Leave(self, node, *args, **kwargs):
    self.leave_functions[node.__class__.__name__](self, node, *args, **kwargs)
