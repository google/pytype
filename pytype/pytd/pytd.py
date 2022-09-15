"""Internal representation of pytd nodes.

All pytd nodes should be frozen attrs inheriting from node.Node (aliased
to Node in this module). Nodes representing types should also inherit from Type.

Since we use frozen classes, setting attributes in __post_init__ needs to be
done via
  object.__setattr__(self, 'attr', value)

NOTE: The way we introspect on the types of the fields requires forward
references to be simple classes, hence use
  x: Union['Foo', 'Bar']
rather than
  x: 'Union[Foo, Bar]'
"""

import enum
import itertools

import typing
from typing import Any, Optional, Tuple, TypeVar, Union

import attrs

from pytype.pytd.parse import node

# Alias node.Node for convenience.
Node = node.Node

_TypeT = TypeVar('_TypeT', bound='Type')


class Type:
  """Each type class below should inherit from this mixin."""
  name: Optional[str]

  # We type-annotate many things as pytd.Type when we'd really want them to be
  # Intersection[pytd.Type, pytd.parse.node.Node], so we need to copy some type
  # signatures from Node here.
  if typing.TYPE_CHECKING:

    def Replace(self: _TypeT, **kwargs) -> _TypeT:
      del kwargs  # unused
      return self

    def Visit(self: _TypeT, visitor, *args, **kwargs) -> _TypeT:
      del visitor, args, kwargs  # unused
      return self

  __slots__ = ()


@attrs.frozen(slots=False, eq=False)
class TypeDeclUnit(Node):
  """Module node. Holds module contents (constants / classes / functions).

  Attributes:
    name: Name of this module, or None for the top-level module.
    constants: Iterable of module-level constants.
    type_params: Iterable of module-level type parameters.
    functions: Iterable of functions defined in this type decl unit.
    classes: Iterable of classes defined in this type decl unit.
    aliases: Iterable of aliases (or imports) for types in other modules.
  """
  name: Optional[str]
  constants: Tuple['Constant', ...]
  type_params: Tuple['TypeParameter', ...]
  classes: Tuple['Class', ...]
  functions: Tuple['Function', ...]
  aliases: Tuple['Alias', ...]

  def _InitCache(self):
    # TODO(b/159053187): Put constants, functions, classes and aliases into a
    # combined dict.
    self.PopulateLookupCache(
        self.constants, self.functions, self.classes, self.aliases)
    for x in self.type_params:
      self._name2item[x.full_name] = x

  def Lookup(self, name):
    """Convenience function: Look up a given name in the global namespace.

    Tries to find a constant, function or class by this name.

    Args:
      name: Name to look up.

    Returns:
      A Constant, Function or Class.

    Raises:
      KeyError: if this identifier doesn't exist.
    """
    try:
      return self._name2item[name]
    except AttributeError:
      self._InitCache()
      return self._name2item[name]

  def Get(self, name):
    """Version of Lookup that returns None instead of raising."""
    try:
      return self._name2item.get(name)
    except AttributeError:
      self._InitCache()
      return self._name2item.get(name)

  def __contains__(self, name):
    return bool(self.Get(name))

  # The hash/eq/ne values are used for caching and speed things up quite a bit.

  def __hash__(self):
    return id(self)

  def __eq__(self, other):
    return id(self) == id(other)

  def __ne__(self, other):
    return id(self) != id(other)


@attrs.frozen(cache_hash=True)
class Constant(Node):
  name: str
  type: Type
  value: Any = None


@attrs.frozen(cache_hash=True)
class Alias(Node):
  """An alias (symbolic link) for a class implemented in some other module.

  Unlike Constant, the Alias is the same type, as opposed to an instance of that
  type. It's generated, among others, from imports - e.g. "from x import y as z"
  will create a local alias "z" for "x.y".
  """
  name: str
  type: Union[Type, Constant, 'Function', 'Module']


@attrs.frozen(cache_hash=True)
class Module(Node):
  """A module imported into the current module, possibly with an alias."""
  name: str
  module_name: str

  @property
  def is_aliased(self):
    return self.name != self.module_name


@attrs.frozen(slots=False, cache_hash=True)
class Class(Node):
  """Represents a class declaration.

  Used as dict/set key, so all components must be hashable.

  Attributes:
    name: Class name (string)
    bases: The super classes of this class (instances of pytd.Type).
    methods: Tuple of methods, classmethods, staticmethods
      (instances of pytd.Function).
    constants: Tuple of constant class attributes (instances of pytd.Constant).
    classes: Tuple of nested classes.
    slots: A.k.a. __slots__, declaring which instance attributes are writable.
    template: Tuple of pytd.TemplateItem instances.
  """
  name: str
  metaclass: Union[None, Type]
  bases: Tuple[Union['Class', Type], ...]
  methods: Tuple['Function', ...]
  constants: Tuple[Constant, ...]
  classes: Tuple['Class', ...]
  decorators: Tuple[Alias, ...]
  slots: Optional[Tuple[str, ...]]
  template: Tuple['TemplateItem', ...]

  def _InitCache(self):
    # TODO(b/159053187): Put constants, functions, classes and aliases into a
    # combined dict.
    self.PopulateLookupCache(self.methods, self.constants, self.classes)

  def Lookup(self, name):
    """Convenience function: Look up a given name in the class namespace.

    Tries to find a method or constant by this name in the class.

    Args:
      name: Name to look up.

    Returns:
      A Constant or Function instance.

    Raises:
      KeyError: if this identifier doesn't exist in this class.
    """
    # TODO(b/159053187): Remove this. Make methods and constants dictionaries.
    try:
      return self._name2item[name]
    except AttributeError:
      self._InitCache()
      return self._name2item[name]

  def Get(self, name):
    """Version of Lookup that returns None instead of raising."""
    try:
      return self._name2item.get(name)
    except AttributeError:
      self._InitCache()
      return self._name2item.get(name)

  def __contains__(self, name):
    return bool(self.Get(name))


class MethodKind(enum.Enum):
  METHOD = 'method'
  STATICMETHOD = 'staticmethod'
  CLASSMETHOD = 'classmethod'
  PROPERTY = 'property'


class MethodFlag(enum.Flag):
  NONE = enum.auto()
  ABSTRACT = enum.auto()
  COROUTINE = enum.auto()
  FINAL = enum.auto()

  @classmethod
  def abstract_flag(cls, is_abstract):  # pylint: disable=invalid-name
    # Useful when creating functions directly (other flags aren't needed there).
    return cls.ABSTRACT if is_abstract else cls.NONE


@attrs.frozen(cache_hash=True)
class Function(Node):
  """A function or a method, defined by one or more PyTD signatures.

  Attributes:
    name: The name of this function.
    signatures: Tuple of possible parameter type combinations for this function.
    kind: The kind of function (e.g., MethodKind.STATICMETHOD).
    flags: A bitfield of flags like is_abstract
  """
  name: str
  signatures: Tuple['Signature', ...]
  kind: MethodKind
  flags: MethodFlag = MethodFlag.NONE

  @property
  def is_abstract(self):
    return bool(self.flags & MethodFlag.ABSTRACT)

  @property
  def is_coroutine(self):
    return bool(self.flags & MethodFlag.COROUTINE)

  @property
  def is_final(self):
    return bool(self.flags & MethodFlag.FINAL)

  def with_flag(self, flag, value):
    """Return a copy of self with flag set to value."""
    new_flags = self.flags | flag if value else self.flags & ~flag
    return self.Replace(flags=new_flags)


@attrs.frozen(cache_hash=True)
class Signature(Node):
  """Represents an individual signature of a function.

  For overloaded functions, this is one specific combination of parameters.
  For non-overloaded functions, there is a 1:1 correspondence between function
  and signature.

  Attributes:
    params: The list of parameters for this function definition.
    starargs: Name of the "*" parameter. The "args" in "*args".
    starstarargs: Name of the "*" parameter. The "kw" in "**kw".
    return_type: The return type of this function.
    exceptions: List of exceptions for this function definition.
    template: names for bindings for bounded types in params/return_type
  """
  params: Tuple['Parameter', ...]
  starargs: Optional['Parameter']
  starstarargs: Optional['Parameter']
  return_type: Type
  exceptions: Tuple[Type, ...]
  template: Tuple['TemplateItem', ...]

  @property
  def name(self):
    return None

  @property
  def has_optional(self):
    return self.starargs is not None or self.starstarargs is not None


class ParameterKind(enum.Enum):
  REGULAR = 'regular'
  POSONLY = 'posonly'
  KWONLY = 'kwonly'


@attrs.frozen(cache_hash=True)
class Parameter(Node):
  """Represents a parameter of a function definition.

  Attributes:
    name: The name of the parameter.
    type: The type of the parameter.
    kind: The kind of parameter (e.g., ParameterKind.KWONLY).
    optional: If the parameter is optional.
    mutated_type: The type the parameter will have after the function is called
      if the type is mutated, None otherwise.
  """
  name: str
  type: Type
  kind: ParameterKind
  optional: bool
  mutated_type: Optional[Type]


@attrs.frozen(cache_hash=True)
class TypeParameter(Node, Type):
  """Represents a type parameter.

  A type parameter is a bound variable in the context of a function or class
  definition. It specifies an equivalence between types.
  For example, this defines an identity function:
    def f(x: T) -> T

  Attributes:
    name: Name of the parameter. E.g. "T".
    scope: Fully-qualified name of the class or function this parameter is
      bound to. E.g. "mymodule.MyClass.mymethod", or None.
  """
  name: str
  constraints: Tuple[Type, ...] = attrs.field(factory=tuple)
  bound: Optional[Type] = None
  scope: Optional[str] = None

  def __lt__(self, other):
    try:
      return super().__lt__(other)
    except TypeError:
      # In Python 3, str and None are not comparable. Declare None to be less
      # than every str so that visitors.AdjustTypeParameters.VisitTypeDeclUnit
      # can sort type parameters.
      return self.scope is None

  @property
  def full_name(self):
    # There are hard-coded type parameters in the code (e.g., T for sequences),
    # so the full name cannot be stored directly in self.name. Note that "" is
    # allowed as a module name.
    return ('' if self.scope is None else self.scope + '.') + self.name

  @property
  def upper_value(self):
    if self.constraints:
      return UnionType(self.constraints)
    elif self.bound:
      return self.bound
    else:
      return AnythingType()


@attrs.frozen(cache_hash=True)
class TemplateItem(Node):
  """Represents template name for generic types.

  This is used for classes and signatures. The 'template' field of both is
  a list of TemplateItems. Note that *using* the template happens through
  TypeParameters.  E.g. in:
    class A<T>:
      def f(T x) -> T
  both the "T"s in the definition of f() are using pytd.TypeParameter to refer
  to the TemplateItem in class A's template.

  Attributes:
    type_param: the TypeParameter instance used. This is the actual instance
      that's used wherever this type parameter appears, e.g. within a class.
  """
  type_param: TypeParameter

  @property
  def name(self):
    return self.type_param.name

  @property
  def full_name(self):
    return self.type_param.full_name


# Types can be:
# 1.) NamedType:
#     Specifies a type or import by name.
# 2.) ClassType
#     Points back to a Class in the AST. (This makes the AST circular)
# 3.) GenericType
#     Contains a base type and parameters.
# 4.) UnionType
#     Can be multiple types at once.
# 5.) NothingType / AnythingType
#     Special purpose types that represent nothing or everything.
# 6.) TypeParameter
#     A placeholder for a type.
# For 1 and 2, the file visitors.py contains tools for converting between the
# corresponding AST representations.


@attrs.frozen(cache_hash=True)
class NamedType(Node, Type):
  """A type specified by name and, optionally, the module it is in."""
  name: str

  def __str__(self):
    return self.name


@attrs.mutable(init=False, slots=False, eq=False)
class ClassType(Node, Type):
  """A type specified through an existing class node."""
  # This type is different from normal nodes:
  # (a) It's mutable, and there are functions
  #     (parse/visitors.py:FillInLocalPointers) that modify a tree in place.
  # (b) The cls pointer is not treated as a regular attr field.
  # (c) Visitors will not process the "children" of this node. Since we point
  #     to classes that are back at the top of the tree, that would generate
  #     cycles.

  name: str = attrs.field()

  # We do not want cls to be a child node, but we do want it to be an optional
  # arg to __init__ and accessible via self.cls
  cls = None

  def __init__(self, name, cls=None):
    self.name = name
    self.cls = cls

  def __eq__(self, other):
    return (self.__class__ == other.__class__ and
            self.name == other.name)

  def __hash__(self):
    return hash((self.__class__.__name__, self.name))

  def __str__(self):
    return str(self.cls.name) if self.cls else self.name

  def __repr__(self):
    return '{type}{cls}({name})'.format(
        type=type(self).__name__, name=self.name,
        cls='<unresolved>' if self.cls is None else '')


@attrs.frozen(cache_hash=True)
class LateType(Node, Type):
  """A type we have yet to resolve."""
  name: str
  recursive: bool = False

  def __str__(self):
    return self.name


@attrs.frozen(cache_hash=True)
class AnythingType(Node, Type):
  """A type we know nothing about yet (? in pytd)."""

  @property
  def name(self):
    return None

  def __bool__(self):
    return True


@attrs.frozen(cache_hash=True)
class NothingType(Node, Type):
  """An "impossible" type, with no instances (nothing in pytd).

  Also known as the "uninhabited" type, or, in type systems, the "bottom" type.
  For representing empty lists, and functions that never return.
  """

  @property
  def name(self):
    return None

  def __bool__(self):
    return True


def _FlattenTypes(type_list) -> Tuple[Type, ...]:
  """Helper function for _SetOfTypes initialization."""
  assert type_list  # Disallow empty sets. Use NothingType for these.
  flattened = itertools.chain.from_iterable(
      t.type_list if isinstance(t, _SetOfTypes) else [t]
      for t in type_list)
  # Remove duplicates, preserving order
  unique = tuple(dict.fromkeys(flattened))
  return unique


@attrs.frozen(eq=False)
class _SetOfTypes(Node, Type):
  """Super class for shared behavior of UnionType and IntersectionType."""
  # NOTE: type_list is kept as a tuple, to preserve the original order
  #       even though in most respects it acts like a frozenset.
  #       It also flattens the input, such that printing without
  #       parentheses gives the same result.
  type_list: Tuple[Type, ...] = attrs.field(converter=_FlattenTypes)

  @property
  def name(self):
    return None

  def __hash__(self):
    # See __eq__ - order doesn't matter, so use frozenset
    return hash(frozenset(self.type_list))

  def __eq__(self, other):
    if self is other:
      return True
    if isinstance(other, type(self)):
      # equality doesn't care about the ordering of the type_list
      return frozenset(self.type_list) == frozenset(other.type_list)
    return NotImplemented

  def __ne__(self, other):
    return not self == other


class UnionType(_SetOfTypes):
  """A union type that contains all types in self.type_list."""
  __slots__ = ()


class IntersectionType(_SetOfTypes):
  """An intersection type."""
  __slots__ = ()


@attrs.frozen(cache_hash=True)
class GenericType(Node, Type):
  """Generic type. Takes a base type and type parameters.

  This is used for homogeneous tuples, lists, dictionaries, user classes, etc.

  Attributes:
    base_type: The base type. Instance of Type.
    parameters: Type parameters. Tuple of instances of Type.
  """
  base_type: Union[NamedType, ClassType, LateType]
  parameters: Tuple[Type, ...]

  @property
  def name(self):
    return self.base_type.name

  @property
  def element_type(self):
    """Type of the contained type, assuming we only have one type parameter."""
    element_type, = self.parameters
    return element_type


class TupleType(GenericType):
  """Special generic type for heterogeneous tuples.

  A tuple with length len(self.parameters), whose item type is specified at
  each index.
  """
  __slots__ = ()


class CallableType(GenericType):
  """Special generic type for a Callable that specifies its argument types.

  A Callable with N arguments has N+1 parameters. The first N parameters are
  the individual argument types, in the order of the arguments, and the last
  parameter is the return type.
  """
  __slots__ = ()

  @property
  def args(self):
    return self.parameters[:-1]

  @property
  def ret(self):
    return self.parameters[-1]


@attrs.frozen(cache_hash=True)
class Literal(Node, Type):
  value: Union[int, str, Type, Constant]

  @property
  def name(self):
    return None


@attrs.frozen(cache_hash=True)
class Annotated(Node, Type):
  base_type: Type
  annotations: Tuple[str, ...]

  @property
  def name(self):
    return None


# Types that can be a base type of GenericType:
GENERIC_BASE_TYPE = (NamedType, ClassType)


def IsContainer(t: Class) -> bool:
  """Checks whether class t is a container."""
  if t.name in ('typing.Generic', 'typing.Protocol'):
    return True
  for p in t.bases:
    if isinstance(p, GenericType):
      base = p.base_type
      if isinstance(base, ClassType) and IsContainer(base.cls):
        return True
  return False


# Singleton objects that will be automatically converted to their types.
# The unqualified form is there so local name resolution can special-case it.
SINGLETON_TYPES = frozenset({'Ellipsis', 'builtins.Ellipsis'})


def ToType(item, allow_constants=False, allow_functions=False,
           allow_singletons=False):
  """Convert a pytd AST item into a type.

  Takes an AST item representing the definition of a type and returns an item
  representing a reference to the type. For example, if the item is a
  pytd.Class, this method will return a pytd.ClassType whose cls attribute
  points to the class.

  Args:
    item: A pytd.Node item.
    allow_constants: When True, constants that cannot be converted to types will
      be passed through unchanged.
    allow_functions: When True, functions that cannot be converted to types will
      be passed through unchanged.
    allow_singletons: When True, singletons that act as their types in
      annotations will return that type.

  Returns:
    A pytd.Type object representing the type of an instance of `item`.
  """
  if isinstance(item, Type):
    return item
  elif isinstance(item, Module):
    return item
  elif isinstance(item, Class):
    return ClassType(item.name, item)
  elif isinstance(item, Function) and allow_functions:
    return item
  elif isinstance(item, Constant):
    if allow_singletons and item.name in SINGLETON_TYPES:
      return item.type
    elif item.type.name == 'builtins.type':
      # A constant whose type is Type[C] is equivalent to class C, so the type
      # of an instance of the constant is C.
      if isinstance(item.type, GenericType):
        return item.type.parameters[0]
      else:
        return AnythingType()
    elif (isinstance(item.type, AnythingType) or
          item.name == 'typing_extensions.TypedDict'):
      # A constant with type Any may be a type, and TypedDict is a class that
      # looks like a constant:
      #   https://github.com/python/typeshed/blob/8cad322a8ccf4b104cafbac2c798413edaa4f327/third_party/2and3/typing_extensions.pyi#L68
      return AnythingType()
    elif allow_constants:
      return item
  elif isinstance(item, Alias):
    return item.type
  raise NotImplementedError(f"Can't convert {type(item)}: {item}")


def AliasMethod(func, from_constant):
  """Returns method func with its signature modified as if it has been aliased.

  Args:
    func: A pytd.Function.
    from_constant: If True, func will be modified as if it has been aliased from
      an instance of its defining class, e.g.,
        class Foo:
          def func(self): ...
        const = ...  # type: Foo
        func = const.func
      Otherwise, it will be modified as if aliased from the class itself:
        class Foo:
          def func(self): ...
        func = Foo.func

  Returns:
    A pytd.Function, the aliased method.
  """
  # We allow module-level aliases of methods from classes and class instances.
  # When a static method is aliased, or a normal method is aliased from a class
  # (not an instance), the entire method signature is copied. Otherwise, the
  # first parameter ('self' or 'cls') is dropped.
  new_func = func.Replace(kind=MethodKind.METHOD)
  if func.kind == MethodKind.STATICMETHOD or (
      func.kind == MethodKind.METHOD and not from_constant):
    return new_func
  return new_func.Replace(signatures=tuple(
      s.Replace(params=s.params[1:]) for s in new_func.signatures))


def LookupItemRecursive(module, name):
  """Recursively look up name in module."""

  def ExtractClass(t):
    if isinstance(t, ClassType) and t.cls:
      return t.cls
    t = module.Get(t.name)
    if isinstance(t, Class):
      return t
    return None

  def Lookup(item, *names):
    for name in names:
      found = item.Get(name)
      if found is not None:
        return found
    return None

  parts = name.split('.')
  partial_name = module.name
  prev_item = None
  item = module

  for part in parts:
    prev_item = item
    # Check the type of item and give up if we encounter a type we don't know
    # how to handle.
    if isinstance(item, Constant):
      found = ExtractClass(item.type)
      if not found:
        raise KeyError(item.type.name)
      item = found
    elif not isinstance(item, (TypeDeclUnit, Class)):
      raise KeyError(name)
    lookup_name = partial_name + '.' + part

    # Nested class names are fully qualified while function names are not, so
    # we try lookup for both naming conventions.
    found = Lookup(item, lookup_name, part)
    if found:
      item = found
    else:
      if not isinstance(item, Class):
        raise KeyError(item)
      for base in item.bases:
        base_cls = ExtractClass(base)
        if base_cls is None:
          raise KeyError(item)
        found = Lookup(base_cls, lookup_name, part)
        if found:  # if not we continue up the MRO
          item = found
          break  # name found!
      else:
        raise KeyError(item)  # unresolved
    if isinstance(item, Constant):
      partial_name += '.' + item.name.rsplit('.', 1)[-1]
    else:
      partial_name = lookup_name
  if isinstance(item, Function):
    return AliasMethod(item, from_constant=isinstance(prev_item, Constant))
  else:
    return item
