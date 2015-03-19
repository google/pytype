"""A set of classes to build paths that represent the name of an abstract value.

A path itself is represented as a sequence of Components of various kinds.
"""

import collections



class Component(collections.namedtuple("ComponentBase", ["name"])):
  """A component of an abstract value path.

  Attributes:
    name: The name of this path element.
  """

  def __str__(self):
    return self.name

  def __repr__(self):
    return "{}({})".format(self.__class__.__name__, self.name)


class Module(Component):
  """A Python module on the path, may be nested.
  """
  pass


class Class(Component):
  """A Class on the path.
  """
  pass


class Attribute(Component):
  """An attribute (data or method) of a class.

  This will always be the last item on the path.
  """
  pass


class Function(Attribute):
  """An attribute of type "function"."""
  pass


class Path(object):
  """The path of a class of function.

  Contains information about how things are nested - e.g. which class a method
  is in, which module a class is in, etc.
  """

  def __init__(self, *path):
    assert all(isinstance(component, Component) for component in path)
    self.path = path

  def __str__(self):
    return ".".join(str(component) for component in self.path)

  def __len__(self):
    return len(self.path)

  def get_innermost_class(self):
    """Returns the innermost containing class, if it exists."""
    if any(isinstance(c, Class) for c in self.path):
      return [c for c in self.path if isinstance(c, Class)][-1]
    else:
      return None

  def get_function(self):
    """Returns the innermost function, if it exists."""
    if any(isinstance(c, Function) for c in self.path):
      return [c for c in self.path if isinstance(c, Function)][-1]
    else:
      return None

  def add(self, *args):
    """Return a new Path with the given components appended."""
    return Path(*(self.path + args))

