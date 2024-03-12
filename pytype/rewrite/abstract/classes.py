"""Abstract representations of classes."""

from typing import List, Mapping, Optional, Sequence

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions as functions_lib


class BaseClass(base.BaseValue):
  """Base representation of a class."""

  def __init__(self, name: str, members: Mapping[str, base.BaseValue]):
    self.name = name
    self.members = members

    # These methods are attributes of individual classes so that they can be
    # easily customized. For example, unittest.TestCase would want to add
    # 'setUpClass' to its setup methods and 'setUp' to its initializers.

    # classmethods called on a class immediately after creation
    self.setup_methods: List[str] = []
    # classmethod called to create a class instance
    self.constructor = '__new__'
    # instance methods called on an instance immediately after creation
    self.initializers = ['__init__', '__post_init__']

  def __repr__(self):
    return f'BaseClass({self.name})'

  def get_attribute(self, name: str) -> Optional[base.BaseValue]:
    return self.members.get(name)

  def instantiate(self) -> 'Instance':
    """Creates an instance of this class."""
    for setup_method_name in self.setup_methods:
      setup_method = self.get_attribute(setup_method_name)
      if isinstance(setup_method, functions_lib.InterpreterFunction):
        _ = setup_method.bind_to(self).analyze()
    constructor = self.get_attribute(self.constructor)
    if constructor:
      raise NotImplementedError('Custom __new__')
    else:
      instance = Instance(self)
    for initializer_name in self.initializers:
      initializer = self.get_attribute(initializer_name)
      if isinstance(initializer, functions_lib.InterpreterFunction):
        _ = initializer.bind_to(instance).analyze()
    return instance


class InterpreterClass(BaseClass):
  """Class defined in the current module."""

  def __init__(
      self, name: str, members: Mapping[str, base.BaseValue],
      functions: Sequence[functions_lib.InterpreterFunction],
      classes: Sequence['InterpreterClass']):
    super().__init__(name, members)
    # Functions and classes defined in this class's body. Unlike 'members',
    # ignores the effects of post-definition transformations like decorators.
    self.functions = functions
    self.classes = classes

  def __repr__(self):
    return f'InterpreterClass({self.name})'


class Instance(base.BaseValue):
  """Instance of a class."""

  def __init__(self, cls: BaseClass):
    self.cls = cls

  def __repr__(self):
    return f'Instance({self.cls.name})'


BUILD_CLASS = base.Singleton('BUILD_CLASS')
