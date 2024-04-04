"""Abstract representations of classes."""

import abc
import dataclasses
import logging

from typing import Dict, Generic, List, Mapping, Optional, Protocol, Sequence, TypeVar

import immutabledict
from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions as functions_lib

log = logging.getLogger(__name__)

_T = TypeVar('_T')


class _HasMembers(Protocol):

  members: Dict[str, base.BaseValue]


@dataclasses.dataclass
class ClassCallReturn:

  instance: 'MutableInstance'

  def get_return_value(self):
    return self.instance


class SimpleClass(base.BaseValue):
  """Class with a name and members."""

  def __init__(
      self,
      ctx: base.ContextType,
      name: str,
      members: Dict[str, base.BaseValue],
      module: Optional[str] = None,
  ):
    super().__init__(ctx)
    self.name = name
    self.members = members
    self.module = module

    # These methods are attributes of individual classes so that they can be
    # easily customized. For example, unittest.TestCase would want to add
    # 'setUpClass' to its setup methods and 'setUp' to its initializers.

    # classmethods called on a class immediately after creation
    self.setup_methods: List[str] = []
    # classmethod called to create a class instance
    self.constructor = '__new__'
    # instance methods called on an instance immediately after creation
    self.initializers = ['__init__']

  def __repr__(self):
    return f'SimpleClass({self.name})'

  @property
  def _attrs(self):
    return (self.name, immutabledict.immutabledict(self.members))

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
      instance = MutableInstance(self._ctx, self)
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
      instance = MutableInstance(self._ctx, self)
    for initializer_name in self.initializers:
      initializer = self.get_attribute(initializer_name)
      if isinstance(initializer, functions_lib.InterpreterFunction):
        _ = initializer.bind_to(instance).call(args)
    return ClassCallReturn(instance)


class InterpreterClass(SimpleClass):
  """Class defined in the current module."""

  def __init__(
      self, ctx: base.ContextType, name: str,
      members: Dict[str, base.BaseValue],
      functions: Sequence[functions_lib.InterpreterFunction],
      classes: Sequence['InterpreterClass']):
    super().__init__(ctx, name, members)
    # Functions and classes defined in this class's body. Unlike 'members',
    # ignores the effects of post-definition transformations like decorators.
    self.functions = functions
    self.classes = classes

  def __repr__(self):
    return f'InterpreterClass({self.name})'


class BaseInstance(base.BaseValue):
  """Instance of a class."""

  members: Mapping[str, base.BaseValue]

  def __init__(self, ctx: base.ContextType, cls: SimpleClass, members):
    super().__init__(ctx)
    self.cls = cls
    self.members = members

  @abc.abstractmethod
  def set_attribute(self, name: str, value: base.BaseValue) -> None: ...

  @property
  def _attrs(self):
    return (self.cls, immutabledict.immutabledict(self.members))

  def get_attribute(self, name: str) -> Optional[base.BaseValue]:
    if name in self.members:
      return self.members[name]
    cls_attribute = self.cls.get_attribute(name)
    if isinstance(cls_attribute, functions_lib.SimpleFunction):
      return cls_attribute.bind_to(self)
    return cls_attribute


class PythonConstant(base.BaseValue, Generic[_T]):
  """Representation of a Python constant."""

  def __init__(self, ctx: base.ContextType, constant: _T):
    super().__init__(ctx)
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  @property
  def _attrs(self):
    return (self.constant,)


class MutableInstance(BaseInstance):
  """Instance of a class."""

  members: Dict[str, base.BaseValue]

  def __init__(self, ctx: base.ContextType, cls: SimpleClass):
    super().__init__(ctx, cls, {})

  def __repr__(self):
    return f'MutableInstance({self.cls.name})'

  def set_attribute(self, name: str, value: base.BaseValue) -> None:
    if name in self.members:
      self.members[name] = base.Union(self._ctx, (self.members[name], value))
    else:
      self.members[name] = value

  def freeze(self) -> 'FrozenInstance':
    return FrozenInstance(self._ctx, self)


class FrozenInstance(BaseInstance):
  """Frozen instance of a class.

  This is used by SimpleClass.instantiate() to create a snapshot of an instance
  whose members map cannot be further modified.
  """

  def __init__(self, ctx: base.ContextType, instance: MutableInstance):
    super().__init__(
        ctx, instance.cls, immutabledict.immutabledict(instance.members))

  def __repr__(self):
    return f'FrozenInstance({self.cls.name})'

  def set_attribute(self, name: str, value: base.BaseValue) -> None:
    # The VM may try to set an attribute on a frozen instance in the process of
    # analyzing a class's methods. This is fine; we just ignore it.
    log.info('Ignoring attribute set on %r: %s -> %r',
             self, name, value)
