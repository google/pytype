"""Abstract representations of classes."""

import dataclasses

from typing import Dict, List, Optional, Protocol, Sequence

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions as functions_lib


class _HasMembers(Protocol):

  members: Dict[str, base.BaseValue]


@dataclasses.dataclass
class ClassCallReturn:

  instance: 'MutableInstance'

  def get_return_value(self):
    return self.instance


class BaseClass(base.BaseValue):
  """Base representation of a class."""

  def __init__(self, name: str, members: Dict[str, base.BaseValue]):
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

  def instantiate(self) -> 'FrozenInstance':
    """Creates an instance of this class."""
    for setup_method_name in self.setup_methods:
      setup_method = self.get_attribute(setup_method_name)
      if isinstance(setup_method, functions_lib.InterpreterFunction):
        _ = setup_method.bind_to(self).analyze()
    constructor = self.get_attribute(self.constructor)
    if constructor:
      raise NotImplementedError('Custom __new__')
    else:
      instance = MutableInstance(self)
    for initializer_name in self.initializers:
      initializer = self.get_attribute(initializer_name)
      if isinstance(initializer, functions_lib.InterpreterFunction):
        _ = initializer.bind_to(instance).analyze()
    return instance.freeze()

  def call(self, args: functions_lib.Args) -> ClassCallReturn:
    constructor = self.get_attribute(self.constructor)
    if constructor:
      raise NotImplementedError('Custom __new__')
    else:
      instance = MutableInstance(self)
    for initializer_name in self.initializers:
      initializer = self.get_attribute(initializer_name)
      if isinstance(initializer, functions_lib.InterpreterFunction):
        _ = initializer.bind_to(instance).call(args)
    return ClassCallReturn(instance)


class InterpreterClass(BaseClass):
  """Class defined in the current module."""

  def __init__(
      self, name: str, members: Dict[str, base.BaseValue],
      functions: Sequence[functions_lib.InterpreterFunction],
      classes: Sequence['InterpreterClass']):
    super().__init__(name, members)
    # Functions and classes defined in this class's body. Unlike 'members',
    # ignores the effects of post-definition transformations like decorators.
    self.functions = functions
    self.classes = classes

  def __repr__(self):
    return f'InterpreterClass({self.name})'


class MutableInstance(base.BaseValue):
  """Instance of a class."""

  def __init__(self, cls: BaseClass):
    self.cls = cls
    self.members: Dict[str, base.BaseValue] = {}

  def __repr__(self):
    return f'MutableInstance({self.cls.name})'

  def get_attribute(self, name: str) -> Optional[base.BaseValue]:
    if name in self.members:
      return self.members[name]
    cls_attribute = self.cls.get_attribute(name)
    if isinstance(cls_attribute, functions_lib.SimpleFunction):
      return cls_attribute.bind_to(self)
    return cls_attribute

  def set_attribute(self, name: str, value: base.BaseValue) -> None:
    if name in self.members:
      raise NotImplementedError(f'Attribute already set: {name}')
    self.members[name] = value

  def freeze(self) -> 'FrozenInstance':
    return FrozenInstance(self)


class FrozenInstance(base.BaseValue):
  """Frozen instance of a class.

  This is used by BaseClass.instantiate() to create a snapshot of an instance
  whose members map cannot be further modified.
  """

  def __init__(self, instance: MutableInstance):
    self._underlying = instance

  @property
  def cls(self):
    return self._underlying.cls

  def get_attribute(self, name: str) -> Optional[base.BaseValue]:
    return self._underlying.get_attribute(name)


BUILD_CLASS = base.Singleton('BUILD_CLASS')
