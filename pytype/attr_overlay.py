"""Support for the 'attrs' library."""

import logging
import textwrap

from pytype import abstract
from pytype import abstract_utils
from pytype import annotations_util
from pytype import function
from pytype import overlay
from pytype.pyi import parser


log = logging.getLogger(__name__)


class AttrOverlay(overlay.Overlay):
  """A custom overlay for the 'attr' module."""

  def __init__(self, vm):
    member_map = {
        "s": Attrs.make,
        "ib": Attrib.make,
        "Factory": Factory.make,
    }
    ast = vm.loader.import_name("attr")
    super(AttrOverlay, self).__init__(vm, "attr", member_map, ast)


class Attrs(abstract.PyTDFunction):
  """Implements the @attr.s decorator."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrs, cls).make(name, vm, "attr")

  def __init__(self, *args, **kwargs):
    super(Attrs, self).__init__(*args, **kwargs)
    # Defaults for the args to attr.s that we support.
    self.args = {
        "init": True,
        "kw_only": False,
        "auto_attribs": False
    }

  def _make_init(self, node, attrs):
    # attrs removes leading underscores from attrib names when
    # generating kwargs for __init__.
    for attr in attrs:
      attr.name = attr.name.lstrip("_")

    annotations = {}
    late_annotations = {}
    for attr in attrs:
      if is_late_annotation(attr.typ):
        late_annotations[attr.name] = attr.typ
      elif all(t.cls for t in attr.typ.data):
        types = attr.typ.data
        if len(types) == 1:
          annotations[attr.name] = types[0].cls
        else:
          t = abstract.Union([t.cls for t in types], self.vm)
          annotations[attr.name] = t

    # The kw_only arg is ignored in python2; using it is not an error.
    params = [x.name for x in attrs]
    if self.args["kw_only"] and self.vm.PY3:
      param_names = ("self",)
      kwonly_params = tuple(params)
    else:
      param_names = ("self",) + tuple(params)
      kwonly_params = ()

    defaults = {x.name: x.default for x in attrs if x.default}

    init = abstract.SimpleFunction(
        name="__init__",
        param_names=param_names,
        varargs_name=None,
        kwonly_params=kwonly_params,
        kwargs_name=None,
        defaults=defaults,
        annotations=annotations,
        late_annotations=late_annotations,
        vm=self.vm)
    if late_annotations:
      self.vm.functions_with_late_annotations.append(init)
    return init.to_variable(node)

  def _update_kwargs(self, args):
    for k, v in args.namedargs.items():
      if k in self.args:
        try:
          self.args[k] = abstract_utils.get_atomic_python_constant(v)
        except abstract_utils.ConversionError:
          self.vm.errorlog.not_supported_yet(
              self.vm.frames,
              "Non-constant attr.s argument %r" % k)

  def _type_clash_error(self, value):
    if is_late_annotation(value):
      err = value.expr
    else:
      err = value.data[0].cls
    self.vm.errorlog.invalid_annotation(self.vm.frames, err)

  def call(self, node, func, args):
    """Processes the attrib members of a class."""
    self.match_args(node, args)

    if args.namedargs:
      self._update_kwargs(args)

    # @attr.s does not take positional arguments in typical usage, but
    # technically this works:
    #   class Foo:
    #     x = attr.ib()
    #   Foo = attr.s(Foo, **kwargs)
    #
    # Unfortunately, it also works to pass kwargs as posargs; we will at least
    # reject posargs if the first arg is not a Callable.
    if not args.posargs:
      return node, self.to_variable(node)

    cls_var = args.posargs[0]
    # We should only have a single binding here
    cls, = cls_var.data

    # Collect classvars to convert them to attrs.
    ordered_locals = self.vm.ordered_locals[cls.name]
    ordered_attrs = []
    late_annotation = False  # True if we find a bare late annotation
    for name, value, orig in ordered_locals:
      if name.startswith("__") and name.endswith("__"):
        continue
      if is_attrib(orig):
        if not is_attrib(value) and orig.data[0].has_type:
          # We cannot have both a type annotation and a type argument.
          self._type_clash_error(value)
          attr = InitParam(name=name,
                           typ=self.vm.new_unsolvable(node),
                           default=None)
        else:
          if is_late_annotation(value):
            attr = InitParam(name=name,
                             typ=value,
                             default=orig.data[0].default)
            cls.members[name] = orig.data[0].typ
          elif is_attrib(value):
            # Replace the attrib in the class dict with its type.
            attr = InitParam(name=name,
                             typ=value.data[0].typ,
                             default=value.data[0].default)
            cls.members[name] = attr.typ
          else:
            # cls.members[name] has already been set via a typecomment
            attr = InitParam(name=name,
                             typ=value,
                             default=orig.data[0].default)
        ordered_attrs.append(attr)
      elif self.args["auto_attribs"]:
        # NOTE: This code should be much of what we need to implement
        # dataclasses too.
        #
        # TODO(b/72678203): typing.ClassVar is the only way to filter a variable
        # out from auto_attribs, but we don't even support importing it.
        attr = InitParam(name=name,
                         typ=value,
                         default=orig)
        if is_late_annotation(value) and orig is None:
          # We are generating a class member from a bare annotation.
          cls.members[name] = self.vm.convert.none.to_variable(node)
          cls.late_annotations[name] = value
          late_annotation = True
        ordered_attrs.append(attr)

    # See if we need to resolve any late annotations
    if late_annotation:
      self.vm.classes_with_late_annotations.append(cls)

    # Add an __init__ method
    if self.args["init"]:
      init_method = self._make_init(node, ordered_attrs)
      cls.members["__init__"] = init_method

    return node, cls_var


class InitParam(object):
  """Parameters for the __init__ method."""

  def __init__(self, name, typ, default):
    self.name = name
    self.typ = typ
    self.default = default


class AttribInstance(abstract.SimpleAbstractValue):
  """Return value of an attr.ib() call."""

  def __init__(self, vm, typ, has_type, default=None):
    super(AttribInstance, self).__init__("attrib", vm)
    self.typ = typ
    self.has_type = has_type
    self.default = default


class Attrib(abstract.PyTDFunction):
  """Implements attr.ib."""

  @classmethod
  def make(cls, name, vm):
    return super(Attrib, cls).make(name, vm, "attr")

  def call(self, node, unused_func, args):
    """Returns a type corresponding to an attr."""
    self.match_args(node, args)
    type_var = args.namedargs.get("type")
    if "default" in args.namedargs and "factory" in args.namedargs:
      # attr.ib(factory=x) is syntactic sugar for attr.ib(default=Factory(x)).
      raise function.DuplicateKeyword(
          self.signatures[0].signature, args, self.vm, "default")
    elif "default" in args.namedargs:
      default_var = args.namedargs["default"]
    elif "factory" in args.namedargs:
      mod = self.vm.import_module("attr", "attr", 0)
      node, attr = self.vm.attribute_handler.get_attribute(node, mod, "Factory")
      # We know there is only one value because Factory is in the overlay.
      factory, = attr.data
      factory_args = function.Args(posargs=(args.namedargs["factory"],))
      node, default_var = factory.call(node, attr.bindings[0], factory_args)
    else:
      default_var = None
    has_type = type_var is not None
    if type_var:
      typ = self._instantiate_type(node, type_var)
    elif default_var:
      typ = self._get_type_from_default(node, default_var)
    else:
      typ = self.vm.new_unsolvable(node)
    typ = AttribInstance(self.vm, typ, has_type, default_var).to_variable(node)
    return node, typ

  def _instantiate_type(self, node, type_var):
    cls = type_var.data[0]
    if isinstance(cls, abstract.AnnotationContainer):
      cls = cls.base_cls
    return cls.instantiate(node)

  def _get_type_from_default(self, node, default_var):
    if default_var and default_var.data == [self.vm.convert.none]:
      # A default of None doesn't give us any information about the actual type.
      return self.vm.program.NewVariable(
          [self.vm.convert.unsolvable], [default_var.bindings[0]], node)
    return default_var


def is_attrib(var):
  if var is None or is_late_annotation(var):
    return False
  return isinstance(var.data[0], AttribInstance)


def is_late_annotation(val):
  return isinstance(val, annotations_util.LateAnnotation)


class Factory(abstract.PyTDFunction):
  """Implementation of attr.Factory."""

  # TODO(rechen): This snippet is necessary because we can't yet parse the
  # typeshed attr stubs and pytype infers the type of attr.Factory as Any.
  # Remove it once
  # https://github.com/google/pytype/issues/321 and
  # https://github.com/google/pytype/issues/315 are fixed and pytype is using
  # the canonical attr stubs.
  PYTD = textwrap.dedent("""
    from typing import Callable, TypeVar
    _T = TypeVar("_T")
    def Factory(factory: Callable[[], _T]) -> _T: ...
  """)

  @classmethod
  def make(cls, name, vm):
    ast = vm.loader.resolve_ast(parser.parse_string(
        cls.PYTD, name="attr", python_version=vm.python_version))
    pyval = ast.Lookup("attr.Factory")
    return super(Factory, cls).make(name, vm, "attr", pyval=pyval)
