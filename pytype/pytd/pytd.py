"""AST representation of a pytd file."""

import collections
import itertools

from pytype.pytd.parse import node
from pytype.pytd.parse import preconditions


# This mixin is used to define the classes that satisfy the {Type}
# precondition.  Each type class below should inherit from this mixin.
# Note that the mixin must be registered with preconditions.register() below.


class Type:

  __slots__ = ()


preconditions.register(Type)


class TypeDeclUnit(node.Node('name: str or None',
                             'constants: tuple[Constant]',
                             'type_params: tuple[TypeParameter]',
                             'classes: tuple[Class]',
                             'functions: tuple[Function]',
                             'aliases: tuple[Alias]')):
  """Module node. Holds module contents (constants / classes / functions).

  Attributes:
    name: Name of this module, or None for the top-level module.
    constants: Iterable of module-level constants.
    type_params: Iterable of module-level type parameters.
    functions: Iterable of functions defined in this type decl unit.
    classes: Iterable of classes defined in this type decl unit.
    aliases: Iterable of aliases (or imports) for types in other modules.
  """

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
    # TODO(b/159053187): Put constants, functions, classes and aliases into a
    # combined dict.
    try:
      return self._name2item[name]
    except AttributeError:
      self._name2item = {}
      for x in self.type_params:
        self._name2item[x.full_name] = x
      for x in self.constants + self.functions + self.classes + self.aliases:
        self._name2item[x.name] = x
      return self._name2item[name]

  # The hash/eq/ne values are used for caching and speed things up quite a bit.

  def __hash__(self):
    return id(self)

  def __eq__(self, other):
    return id(self) == id(other)

  def __ne__(self, other):
    return id(self) != id(other)


class Constant(node.Node('name: str', 'type: {Type}')):
  __slots__ = ()


class Alias(node.Node('name: str', 'type: {Type} or Constant or Function')):
  """An alias (symbolic link) for a class implemented in some other module.

  Unlike Constant, the Alias is the same type, as opposed to an instance of that
  type. It's generated, among others, from imports - e.g. "from x import y as z"
  will create a local alias "z" for "x.y".
  """
  __slots__ = ()


class Module(node.Node('name: str', 'module_name: str')):
  """A module imported into the current module, possibly with an alias."""
  __slots__ = ()

  @property
  def is_aliased(self):
    return self.name != self.module_name


class Class(node.Node('name: str',
                      'metaclass: None or {Type}',
                      'parents: tuple[Class or {Type}]',
                      'methods: tuple[Function]',
                      'constants: tuple[Constant]',
                      'classes: tuple[Class]',
                      'decorators: tuple[Function or {Type}]',
                      'slots: None or tuple[str]',
                      'template: tuple[TemplateItem]')):
  """Represents a class declaration.

  Used as dict/set key, so all components must be hashable.

  Attributes:
    name: Class name (string)
    parents: The super classes of this class (instances of pytd.Type).
    methods: Tuple of methods, classmethods, staticmethods
      (instances of pytd.Function).
    constants: Tuple of constant class attributes (instances of pytd.Constant).
    classes: Tuple of nested classes.
    slots: A.k.a. __slots__, declaring which instance attributes are writable.
    template: Tuple of pytd.TemplateItem instances.
  """
  # TODO(b/159053187): Rename "parents" to "bases". "Parents" is confusing since
  # we're in a tree.

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
      self._name2item = {}
      for x in self.methods + self.constants + self.classes:
        self._name2item[x.name] = x
      return self._name2item[name]


STATICMETHOD, CLASSMETHOD, METHOD, PROPERTY = (
    'staticmethod', 'classmethod', 'method', 'property')


class Function(node.Node('name: str',
                         'signatures: tuple[Signature]',
                         'kind: str',
                         'flags: int')):
  """A function or a method, defined by one or more PyTD signatures.

  Attributes:
    name: The name of this function.
    signatures: Tuple of possible parameter type combinations for this function.
    kind: The type of this function. One of: STATICMETHOD, CLASSMETHOD, METHOD
    flags: A bitfield of flags like is_abstract
  """
  __slots__ = ()
  IS_ABSTRACT = 1
  IS_COROUTINE = 2

  def __new__(cls, name, signatures, kind, flags=0):
    self = super(Function, cls).__new__(cls, name, signatures, kind, flags)
    return self

  def _set_flag(self, flag, enable):
    if enable:
      self.flags |= flag
    else:
      self.flags |= ~flag

  @property
  def is_abstract(self):
    return self.flags & self.IS_ABSTRACT

  @is_abstract.setter
  def is_abstract(self, value):
    self._set_flag(self.IS_ABSTRACT, value)

  @property
  def is_coroutine(self):
    return self.flags & self.IS_COROUTINE

  @is_coroutine.setter
  def is_coroutine(self, value):
    self._set_flag(self.IS_COROUTINE, value)

  @classmethod
  def abstract_flag(cls, is_abstract):
    # Temporary hack to support existing code that creates a Function
    # TODO(b/159053187): Implement a common flag bitmap for all function types
    return cls.IS_ABSTRACT if is_abstract else 0


class Signature(node.Node('params: tuple[Parameter]',
                          'starargs: Parameter or None',
                          'starstarargs: Parameter or None',
                          'return_type: {Type}',
                          'exceptions: tuple[{Type}]',
                          'template: tuple[TemplateItem]')):
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
  __slots__ = ()

  @property
  def name(self):
    return None

  @property
  def has_optional(self):
    return self.starargs is not None or self.starstarargs is not None


class Parameter(node.Node('name: str',
                          'type: {Type}',
                          'kwonly: bool',
                          'optional: bool',
                          'mutated_type: {Type} or None')):
  """Represents a parameter of a function definition.

  Attributes:
    name: The name of the parameter.
    type: The type of the parameter.
    kwonly: True if this parameter can only be passed as a keyword parameter.
    optional: If the parameter is optional.
    mutated_type: The type the parameter will have after the function is called
      if the type is mutated, None otherwise.
  """
  __slots__ = ()


class TypeParameter(node.Node('name: str',
                              'constraints: tuple[{Type}]',
                              'bound: {Type} or None',
                              'scope: str or None'), Type):
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
  __slots__ = ()

  def __new__(cls, name, constraints=(), bound=None, scope=None):
    return super(TypeParameter, cls).__new__(
        cls, name, constraints, bound, scope)

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


class TemplateItem(node.Node('type_param: TypeParameter')):
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
  __slots__ = ()

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


class NamedType(node.Node('name: str'), Type):
  """A type specified by name and, optionally, the module it is in."""
  __slots__ = ()

  def __str__(self):
    return self.name


class ClassType(node.Node('name: str'), Type):
  """A type specified through an existing class node."""

  # This type is different from normal nodes:
  # (a) It's mutable, and there are functions
  #     (parse/visitors.py:FillInLocalPointers) that modify a tree in place.
  # (b) Because it's mutable, it's not actually using the tuple/Node interface
  #     to store things (in particular, the pointer to the existing class).
  # (c) Visitors will not process the "children" of this node. Since we point
  #     to classes that are back at the top of the tree, that would generate
  #     cycles.

  def __getnewargs__(self):
    # Due to a peculiarity of cPickle, the new args cannot have references back
    # into the tree, so we only set name (a string) as a newarg, and set
    # cls to its actual value through getstate/setstate.
    return self.name, None

  def __getstate__(self):
    return (self.cls,)

  def __setstate__(self, state):
    self.cls = state[0]

  def __new__(pycls, name, cls=None):  # pylint: disable=bad-classmethod-argument
    self = super(ClassType, pycls).__new__(pycls, name)
    # self.cls potentially filled in later (by visitors.FillInLocalPointers)
    self.cls = cls
    return self

  # __eq__ is inherited (using tuple equality + requiring the two classes
  #                      be the same)

  def __str__(self):
    return str(self.cls.name) if self.cls else self.name

  def __repr__(self):
    return '{type}{cls}({name})'.format(
        type=type(self).__name__, name=self.name,
        cls='<unresolved>' if self.cls is None else '')


class LateType(node.Node('name: str'), Type):
  """A type we have yet to resolve."""

  def __str__(self):
    return self.name


class AnythingType(node.Node(), Type):
  """A type we know nothing about yet ('?' in pytd)."""
  __slots__ = ()

  @property
  def name(self):
    return None

  def __bool__(self):
    return True


class NothingType(node.Node(), Type):
  """An "impossible" type, with no instances ('nothing' in pytd).

  Also known as the "uninhabited" type, or, in type systems, the "bottom" type.
  For representing empty lists, and functions that never return.
  """
  __slots__ = ()

  @property
  def name(self):
    return None

  def __bool__(self):
    return True


class _SetOfTypes(node.Node('type_list: tuple[{Type}]'), Type):
  """Super class for shared behavior of UnionType and IntersectionType."""

  __slots__ = ()

  # NOTE: type_list is kept as a tuple, to preserve the original order
  #       even though in most respects it acts like a frozenset.
  #       It also flattens the input, such that printing without
  #       parentheses gives the same result.

  def __new__(cls, type_list):
    assert type_list  # Disallow empty sets. Use NothingType for these.
    flattened = itertools.chain.from_iterable(
        t.type_list if isinstance(t, cls) else [t] for t in type_list)

    # Remove duplicates, preserving order
    unique = tuple(collections.OrderedDict.fromkeys(flattened))

    return super(_SetOfTypes, cls).__new__(cls, unique)

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


class IntersectionType(_SetOfTypes):
  """An intersection type."""


class GenericType(node.Node('base_type: NamedType or ClassType or LateType',
                            'parameters: tuple[{Type}]'), Type):
  """Generic type. Takes a base type and type parameters.

  This is used for homogeneous tuples, lists, dictionaries, user classes, etc.

  Attributes:
    base_type: The base type. Instance of Type.
    parameters: Type parameters. Tuple of instances of Type.
  """
  __slots__ = ()

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


class Literal(node.Node('value: int or str or {Type}'), Type):
  __slots__ = ()

  @property
  def name(self):
    return None


# Types that can be a base type of GenericType:
GENERIC_BASE_TYPE = (NamedType, ClassType)


def IsContainer(t):
  assert isinstance(t, Class)
  if t.name == 'typing.Generic':
    return True
  for p in t.parents:
    if isinstance(p, GenericType):
      base = p.base_type
      if isinstance(base, ClassType) and IsContainer(base.cls):
        return True
  return False


def ToType(item, allow_constants=False, allow_functions=False):
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
  elif (isinstance(item, Constant) and item.type.name == 'builtins.type'):
    # A constant whose type is Type[C] is equivalent to class C, so the type of
    # an instance of the constant is C.
    if isinstance(item.type, GenericType):
      return item.type.parameters[0]
    else:
      return AnythingType()
  elif isinstance(item, Constant) and (
      isinstance(item.type, AnythingType) or
      item.type.name == 'typing_extensions._SpecialForm' or
      item.name == 'typing_extensions.TypedDict'):
    # The following constants are treated as (unknown) types:
    # * one whose type is Any or typing_extensions._SpecialForm
    # * one whose name is typing_extensions.TypedDict, as TypedDict is a class
    #   that looks like a constant:
    #   https://github.com/python/typeshed/blob/8cad322a8ccf4b104cafbac2c798413edaa4f327/third_party/2and3/typing_extensions.pyi#L68
    return AnythingType()
  elif isinstance(item, Constant) and allow_constants:
    return item
  elif isinstance(item, Alias):
    return item.type
  else:
    raise NotImplementedError("Can't convert %s: %s" % (type(item), item))
