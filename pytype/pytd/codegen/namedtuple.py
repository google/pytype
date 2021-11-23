"""Generate pytd classes for named tuples."""

from typing import Any, List, Tuple

from pytype.pytd import escape
from pytype.pytd import pytd
from pytype.pytd.codegen import function
from pytype.pytd.codegen import pytdgen


# Attributes that all namedtuple instances have.
_NAMEDTUPLE_MEMBERS = ("_asdict", "__dict__", "_fields", "__getnewargs__",
                       "__getstate__", "_make", "_replace")


class NamedTuple:
  """Construct a class for a new named tuple."""

  def __init__(self, base_name, fields, generated_classes):
    # Handle previously defined NamedTuples with the same name
    index = len(generated_classes[base_name])
    self.name = escape.pack_namedtuple_base_class(base_name, index)
    self.type_param = None  # will be filled in by _new_named_tuple
    self.cls = self._new_named_tuple(self.name, fields)

  def _new_named_tuple(
      self,
      class_name: str,
      fields: List[Tuple[str, Any]]
  ) -> pytd.Class:
    """Generates a pytd class for a named tuple.

    Args:
      class_name: The name of the generated class
      fields: A list of (name, type) tuples.

    Returns:
      A generated class that describes the named tuple.
    """
    class_base = pytdgen.heterogeneous_tuple(
        pytd.NamedType("tuple"),
        tuple(t for _, t in fields))
    class_constants = tuple(pytd.Constant(n, t) for n, t in fields)
    # Since the user-defined fields are the only namedtuple attributes commonly
    # used, we define all the other attributes as Any for simplicity.
    class_constants += tuple(pytd.Constant(name, pytd.AnythingType())
                             for name in _NAMEDTUPLE_MEMBERS)
    methods = function.merge_method_signatures(
        [self._make_new(class_name, fields), self._make_init()])
    return pytd.Class(name=class_name,
                      metaclass=None,
                      bases=(class_base,),
                      methods=tuple(methods),
                      constants=class_constants,
                      decorators=(),
                      classes=(),
                      slots=tuple(n for n, _ in fields),
                      template=())

  def _make_new(
      self,
      name: str,
      fields: List[Tuple[str, Any]]
  ) -> function.NameAndSig:
    """Build a __new__ method for a namedtuple with the given fields.

    For a namedtuple defined as NamedTuple("_", [("foo", int), ("bar", str)]),
    generates the method
      def __new__(cls: Type[_T], foo: int, bar: str) -> _T: ...
    where _T is a TypeVar bounded by the class type.

    Args:
      name: The class name.
      fields: A list of (name, type) pairs representing the namedtuple fields.

    Returns:
      A function.NameAndSig object for a __new__ method.
    """
    type_param = pytd.TypeParameter("_T" + name, bound=pytd.NamedType(name))
    self.type_param = type_param
    cls_arg = ("cls", pytdgen.pytd_type(type_param))
    args = [cls_arg] + fields
    return function.NameAndSig.make("__new__", args, type_param)

  def _make_init(self) -> function.NameAndSig:
    """Build an __init__ method for a namedtuple.

    Builds a dummy __init__ that accepts any arguments. Needed because our
    model of builtins.tuple uses __init__.

    Returns:
      A function.NameAndSig object for an __init__ method.
    """
    self_arg = function.Param("self", pytd.AnythingType()).to_pytd()
    ret = pytd.NamedType("NoneType")
    sig = pytd.Signature(params=(self_arg,), return_type=ret,
                         starargs=function.pytd_default_star_param(),
                         starstarargs=function.pytd_default_starstar_param(),
                         exceptions=(), template=())
    return function.NameAndSig("__init__", sig)
