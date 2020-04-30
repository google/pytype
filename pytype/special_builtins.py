# lint-as: python3

"""Custom implementations of builtin types."""

from pytype import abstract
from pytype import abstract_utils
from pytype import function
from pytype import mixin


class TypeNew(abstract.PyTDFunction):
  """Implements type.__new__."""

  def call(self, node, func, args):
    if len(args.posargs) == 4:
      self.match_args(node, args)  # May raise FailedFunctionCall.
      cls, name_var, bases_var, class_dict_var = args.posargs
      try:
        bases = list(abstract_utils.get_atomic_python_constant(bases_var))
        if not bases:
          bases = [
              self.vm.convert.object_type.to_variable(self.vm.root_cfg_node)]
        node, variable = self.vm.make_class(
            node, name_var, bases, class_dict_var, cls)
      except abstract_utils.ConversionError:
        pass
      else:
        return node, variable
    elif (args.posargs and self.vm.callself_stack and
          args.posargs[-1].data == self.vm.callself_stack[-1].data):
      # We're calling type(self) in an __init__ method. A common pattern for
      # making a class non-instantiable is:
      #   class Foo:
      #     def __init__(self):
      #       if type(self) is Foo:
      #         raise ...
      # If we were to return 'Foo', pytype would think that this constructor
      # can never return. The correct return type is something like
      # TypeVar(bound=Foo), but we can't introduce a type parameter that isn't
      # bound to a class or function, so we'll go with Any.
      self.match_args(node, args)  # May raise FailedFunctionCall.
      return node, self.vm.new_unsolvable(node)
    node, raw_ret = super(TypeNew, self).call(node, func, args)
    # Removes TypeVars from the return value.
    # See test_typevar.TypeVarTest.test_type_of_typevar(_error).
    ret = self.vm.program.NewVariable()
    for b in raw_ret.bindings:
      value = self.vm.annotations_util.deformalize(b.data)
      ret.AddBinding(value, {b}, node)
    return node, ret


class BuiltinFunction(abstract.PyTDFunction):
  """Implementation of functions in __builtin__.pytd."""

  name = None

  @classmethod
  def make(cls, vm):
    assert cls.name
    return super(BuiltinFunction, cls).make(cls.name, vm, "__builtin__")

  def get_underlying_method(self, node, receiver, method_name):
    """Get the bound method that a built-in function delegates to."""
    results = []
    for b in receiver.bindings:
      node, result = self.vm.attribute_handler.get_attribute(
          node, b.data, method_name, valself=b)
      if result is not None:
        results.append(result)
    if results:
      return node, self.vm.join_variables(node, results)
    else:
      return node, None


def get_file_mode(sig, args):
  callargs = {name: var for name, var, _ in sig.signature.iter_args(args)}
  if "mode" in callargs:
    return abstract_utils.get_atomic_python_constant(callargs["mode"])
  else:
    return ""


class Open(BuiltinFunction):
  """Implementation of open(...)."""

  name = "open"

  def call(self, node, func, args):
    if self.vm.PY3:
      # In Python 3, the type of IO object returned depends on the mode.
      self.match_args(node, args)  # May raise FailedFunctionCall.
      sig, = self.signatures
      try:
        mode = get_file_mode(sig, args)
      except abstract_utils.ConversionError:
        pass
      else:
        # The default mode is 'r'.
        io_type = "Binary" if "b" in mode else "Text"
        return node, self.vm.convert.constant_to_var(abstract_utils.AsInstance(
            self.vm.lookup_builtin("typing.%sIO" % io_type)), {}, node)
    return super(Open, self).call(node, func, args)


class Abs(BuiltinFunction):
  """Implements abs."""

  name = "abs"

  def call(self, node, _, args):
    self.match_args(node, args)
    arg = args.posargs[0]
    node, fn = self.get_underlying_method(node, arg, "__abs__")
    if fn is not None:
      return self.vm.call_function(node, fn, function.Args(()))
    else:
      return node, self.vm.new_unsolvable(node)


class Next(BuiltinFunction):
  """Implements next."""

  name = "next"

  def _get_args(self, args):
    arg = args.posargs[0]
    if len(args.posargs) > 1:
      default = args.posargs[1]
    elif "default" in args.namedargs:
      default = args.namedargs["default"]
    else:
      default = self.vm.program.NewVariable()
    return arg, default

  def call(self, node, _, args):
    self.match_args(node, args)
    arg, default = self._get_args(args)
    node, fn = self.get_underlying_method(node, arg, self.vm.convert.next_attr)
    if fn is not None:
      node, ret = self.vm.call_function(node, fn, function.Args(()))
      ret.PasteVariable(default)
      return node, ret
    else:
      # TODO(kramm): This needs a test case.
      return node, self.vm.new_unsolvable(node)


class Filter(BuiltinFunction):
  """Implementation of filter(...)."""

  name = "filter"

  def _filter_pyval(self, data, node):
    """Filter None and False out of literal lists and tuples."""
    if not isinstance(data, (abstract.List, abstract.Tuple)):
      return None
    remove = ([self.vm.convert.none], [self.vm.convert.false])
    pyval = [x for x in data.pyval if x.data not in remove]
    if len(pyval) < len(data.pyval):
      return type(data)(pyval, data.vm).to_variable(node)
    return None

  def _filter_unions(self, data, node):
    """Remove None from any Union type parameters in data."""
    param = data.cls.get_formal_type_parameter(abstract_utils.T)
    if not param.isinstance_Union():
      return None
    new_opts = [x for x in param.options if x.name != "NoneType"]
    if not new_opts:
      return None
    typ = self.vm.merge_values(new_opts)
    cls = data.cls
    params = {**cls.formal_type_parameters, abstract_utils.T: typ}
    new_cls = type(cls)(cls.base_cls, params, cls.vm, cls.template)
    return new_cls.instantiate(node)

  def _filter_none(self, data, node):
    if isinstance(data, abstract.Unsolvable):
      return None
    elif not data.cls:
      return None
    elif isinstance(data, mixin.PythonConstant):
      return self._filter_pyval(data, node)
    else:
      return self._filter_unions(data, node)
    return None

  def call(self, node, func, args):
    self.match_args(node, args)
    if len(args.posargs) != 2:
      return super(Filter, self).call(node, func, args)
    pred, seq = args.posargs
    # Special case filter(None, seq). We remove None from seq and then call the
    # regular filter() so we don't need to reimplement eveything.
    if pred.data == [self.vm.convert.none]:
      result = self.vm.program.NewVariable()
      for b in seq.bindings:
        ret = self._filter_none(b.data, node)
        if ret:
          result.PasteVariable(ret, node, {b})
        else:
          result.PasteBinding(b)
      args = function.Args((pred, result))
    return super(Filter, self).call(node, func, args)


class ObjectPredicate(BuiltinFunction):
  """The base class for builtin predicates of the form f(obj, ...) -> bool.

  Subclasses should implement run() for a specific signature.
  (See UnaryPredicate and BinaryPredicate for examples.)
  """

  def __init__(self, name, signatures, kind, vm):
    super(ObjectPredicate, self).__init__(name, signatures, kind, vm)
    # Map of True/False/None (where None signals an ambiguous bool) to
    # vm values.
    self._vm_values = {
        True: vm.convert.true,
        False: vm.convert.false,
        None: vm.convert.primitive_class_instances[bool],
    }

  def call(self, node, _, args):
    try:
      self.match_args(node, args)
      node = node.ConnectNew(self.name)
      result = self.vm.program.NewVariable()
      self.run(node, args, result)
    except function.InvalidParameters as ex:
      self.vm.errorlog.invalid_function_call(self.vm.frames, ex)
      result = self.vm.new_unsolvable(node)
    return node, result


class UnaryPredicate(ObjectPredicate):
  """The base class for builtin predicates of the form f(obj).

  Subclasses need to override the following:

  _call_predicate(self, node, obj): The implementation of the predicate.
  """

  def run(self, node, args, result):
    for obj in args.posargs[0].bindings:
      node, pyval = self._call_predicate(node, obj)
      result.AddBinding(self._vm_values[pyval],
                        source_set=(obj,), where=node)


class BinaryPredicate(ObjectPredicate):
  """The base class for builtin predicates of the form f(obj, value).

  Subclasses need to override the following:

  _call_predicate(self, node, left, right): The implementation of the predicate.
  """

  def run(self, node, args, result):
    for left in args.posargs[0].bindings:
      for right in args.posargs[1].bindings:
        node, pyval = self._call_predicate(node, left, right)
        result.AddBinding(self._vm_values[pyval],
                          source_set=(left, right), where=node)


class HasAttr(BinaryPredicate):
  """The hasattr() function."""

  name = "hasattr"

  def _call_predicate(self, node, left, right):
    return self._has_attr(node, left.data, right.data)

  def _has_attr(self, node, obj, attr):
    """Check if the object has attribute attr.

    Args:
      node: The given node.
      obj: An AtomicAbstractValue, generally the left hand side of a
          hasattr() call.
      attr: An AtomicAbstractValue, generally the right hand side of a
          hasattr() call.

    Returns:
      (node, result) where result = True if the object has attribute attr, False
      if it does not, and None if it is ambiguous.
    """
    if isinstance(obj, abstract.AMBIGUOUS_OR_EMPTY):
      return node, None
    # If attr is not a literal constant, don't try to resolve it.
    if (not isinstance(attr, mixin.PythonConstant) or
        not isinstance(attr.pyval, str)):
      return node, None
    node, ret = self.vm.attribute_handler.get_attribute(node, obj, attr.pyval)
    return node, ret is not None


def _flatten(value, classes):
  """Flatten the contents of value into classes.

  If value is a Class, it is appended to classes.
  If value is a PythonConstant of type tuple, then each element of the tuple
  that has a single binding is also flattened.
  Any other type of value, or tuple elements that have multiple bindings are
  ignored.

  Args:
    value: An abstract value.
    classes: A list to be modified.

  Returns:
    True iff a value was ignored during flattening.
  """
  # Used by IsInstance and IsSubclass
  if isinstance(value, mixin.Class):
    # A single class, no ambiguity.
    classes.append(value)
    return False
  elif isinstance(value, abstract.Tuple):
    # A tuple, need to process each element.
    ambiguous = False
    for var in value.pyval:
      if (len(var.bindings) != 1 or
          _flatten(var.bindings[0].data, classes)):
        # There were either multiple bindings or ambiguity deeper in the
        # recursion.
        ambiguous = True
    return ambiguous
  else:
    return True


def _check_against_mro(vm, target, class_spec):
  """Check if any of the classes are in the target's MRO.

  Args:
    vm: The virtual machine.
    target: An AtomicAbstractValue whose MRO will be checked.
    class_spec: A Class or PythonConstant tuple of classes (i.e. the second
      argument to isinstance or issubclass).

  Returns:
    True if any class in classes is found in the target's MRO,
    False if no match is found and None if it's ambiguous.
  """
  # Determine the flattened list of classes to check.
  classes = []
  ambiguous = _flatten(class_spec, classes)

  for c in classes:
    if vm.matcher.match_from_mro(target, c, allow_compat_builtins=False):
      return True  # A definite match.
  # No matches, return result depends on whether _flatten() was
  # ambiguous.
  return None if ambiguous else False


class IsInstance(BinaryPredicate):
  """The isinstance() function."""

  name = "isinstance"

  def _call_predicate(self, node, left, right):
    return node, self._is_instance(left.data, right.data)

  def _is_instance(self, obj, class_spec):
    """Check if the object matches a class specification.

    Args:
      obj: An AtomicAbstractValue, generally the left hand side of an
          isinstance() call.
      class_spec: An AtomicAbstractValue, generally the right hand side of an
          isinstance() call.

    Returns:
      True if the object is derived from a class in the class_spec, False if
      it is not, and None if it is ambiguous whether obj matches class_spec.
    """
    cls = obj.get_class()
    if (isinstance(obj, abstract.AMBIGUOUS_OR_EMPTY) or cls is None or
        isinstance(cls, abstract.AMBIGUOUS_OR_EMPTY)):
      return None
    return _check_against_mro(self.vm, cls, class_spec)


class IsSubclass(BinaryPredicate):
  """The issubclass() function."""

  name = "issubclass"

  def _call_predicate(self, node, left, right):
    return node, self._is_subclass(left.data, right.data)

  def _is_subclass(self, cls, class_spec):
    """Check if the given class is a subclass of a class specification.

    Args:
      cls: An AtomicAbstractValue, the first argument to an issubclass call.
      class_spec: An AtomicAbstractValue, the second issubclass argument.

    Returns:
      True if the class is a subclass (or is a class) in the class_spec, False
      if not, and None if it is ambiguous.
    """

    if isinstance(cls, abstract.AMBIGUOUS_OR_EMPTY):
      return None

    return _check_against_mro(self.vm, cls, class_spec)


class IsCallable(UnaryPredicate):
  """The callable() function."""

  name = "callable"

  def _call_predicate(self, node, obj):
    return self._is_callable(node, obj)

  def _is_callable(self, node, obj):
    """Check if the object is callable.

    Args:
      node: The given node.
      obj: An AtomicAbstractValue, the arg of a callable() call.

    Returns:
      (node, result) where result = True if the object is callable,
      False if it is not, and None if it is ambiguous.
    """
    # NOTE: This duplicates logic in the matcher; if this function gets any
    # longer consider calling matcher._match_value_against_type(obj,
    # convert.callable) instead.
    val = obj.data
    if isinstance(val, abstract.AMBIGUOUS_OR_EMPTY):
      return node, None
    # Classes are always callable.
    if isinstance(val, mixin.Class):
      return node, True
    # Otherwise, see if the object has a __call__ method.
    node, ret = self.vm.attribute_handler.get_attribute(
        node, val, "__call__", valself=obj)
    return node, ret is not None


class BuiltinClass(abstract.PyTDClass):
  """Implementation of classes in __builtin__.pytd.

  The module name is passed in to allow classes in other modules to subclass a
  module in __builtin__ and inherit the custom behaviour.
  """

  def __init__(self, vm, name, module="__builtin__"):
    if module == "__builtin__":
      pytd_cls = vm.lookup_builtin("__builtin__.%s" % name)
    else:
      ast = vm.loader.import_name(module)
      pytd_cls = ast.Lookup("%s.%s" % (module, name))
    super(BuiltinClass, self).__init__(name, pytd_cls, vm)
    self.module = module


class SuperInstance(abstract.AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.cls = self.vm.convert.super_type
    self.super_cls = cls
    self.super_obj = obj
    self.get = abstract.NativeFunction("__get__", self.get, self.vm)

  def get(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def _get_descriptor_from_superclass(self, node, cls):
    obj = cls.instantiate(node)
    ret = []
    for b in obj.bindings:
      _, attr = self.vm.attribute_handler.get_attribute(
          node, b.data, "__get__", valself=b)
      if attr:
        ret.append(attr)
    if ret:
      return self.vm.join_variables(node, ret)
    return None

  def get_special_attribute(self, node, name, valself):
    if name == "__get__":
      for cls in self.super_cls.mro[1:]:
        attr = self._get_descriptor_from_superclass(node, cls)
        if attr:
          return attr
      # If we have not successfully called __get__ on an instance of the
      # superclass, fall back to returning self.
      return self.get.to_variable(node)
    else:
      return super(SuperInstance, self).get_special_attribute(
          node, name, valself)

  def get_class(self):
    return self.cls

  def call(self, node, _, args):
    self.vm.errorlog.not_callable(self.vm.frames, self)
    return node, self.vm.new_unsolvable(node)


class Super(BuiltinClass):
  """The super() function. Calling it will create a SuperInstance."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature.from_param_names("super", ("cls", "self"))

  def __init__(self, vm):
    super(Super, self).__init__(vm, "super")

  def call(self, node, _, args):
    result = self.vm.program.NewVariable()
    num_args = len(args.posargs)
    if num_args == 0 and self.vm.PY3:
      # The implicit type argument is available in a freevar named '__class__'.
      cls_var = None
      for i, free_var in enumerate(self.vm.frame.f_code.co_freevars):
        if free_var == abstract.BuildClass.CLOSURE_NAME:
          cls_var = self.vm.frame.cells[
              len(self.vm.frame.f_code.co_cellvars) + i]
          break
      if not (cls_var and cls_var.bindings):
        self.vm.errorlog.invalid_super_call(
            self.vm.frames, message="Missing __class__ closure for super call.",
            details="Is 'super' being called from a method defined in a class?")
        return node, self.vm.new_unsolvable(node)
      # The implicit super object argument is the first positional argument to
      # the function calling 'super'.
      self_arg = self.vm.frame.first_posarg
      if not self_arg:
        self.vm.errorlog.invalid_super_call(
            self.vm.frames, message="Missing 'self' argument to 'super' call.")
        return node, self.vm.new_unsolvable(node)
      super_objects = self_arg.bindings
    elif 1 <= num_args <= 2:
      cls_var = args.posargs[0]
      super_objects = args.posargs[1].bindings if num_args == 2 else [None]
    else:
      raise function.WrongArgCount(self._SIGNATURE, args, self.vm)
    for cls in cls_var.bindings:
      if not isinstance(cls.data, (mixin.Class, abstract.AMBIGUOUS_OR_EMPTY)):
        bad = function.BadParam(
            name="cls", expected=self.vm.convert.type_type)
        raise function.WrongArgTypes(
            self._SIGNATURE, args, self.vm, bad_param=bad)
      for obj in super_objects:
        if obj:
          result.AddBinding(
              SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
        else:
          result.AddBinding(
              SuperInstance(cls.data, None, self.vm), [cls], node)
    return node, result


class Object(BuiltinClass):
  """Implementation of __builtin__.object."""

  def __init__(self, vm):
    super(Object, self).__init__(vm, "object")

  def is_object_new(self, func):
    """Whether the given function is object.__new__.

    Args:
      func: A function.

    Returns:
      True if func equals either of the pytd definitions for object.__new__,
      False otherwise.
    """
    self.load_lazy_attribute("__new__")
    self.load_lazy_attribute("__new__extra_args")
    return ([func] == self.members["__new__"].data or
            [func] == self.members["__new__extra_args"].data)

  def _has_own(self, node, cls, method):
    """Whether a class has its own implementation of a particular method.

    Args:
      node: The current node.
      cls: A mixin.Class.
      method: The method name. So that we don't have to handle the cases when
        the method doesn't exist, we only support "__new__" and "__init__".

    Returns:
      True if the class's definition of the method is different from the
      definition in __builtin__.object, False otherwise.
    """
    assert method in ("__new__", "__init__")
    if not isinstance(cls, mixin.Class):
      return False
    self.load_lazy_attribute(method)
    obj_method = self.members[method]
    _, cls_method = self.vm.attribute_handler.get_attribute(node, cls, method)
    return obj_method.data != cls_method.data

  def get_special_attribute(self, node, name, valself):
    # Based on the definitions of object_init and object_new in
    # cpython/Objects/typeobject.c (https://goo.gl/bTEBRt). It is legal to pass
    # extra arguments to object.__new__ if the calling class overrides
    # object.__init__, and vice versa.
    if valself and not abstract_utils.equivalent_to(valself, self):
      val = valself.data
      if name == "__new__" and self._has_own(node, val, "__init__"):
        self.load_lazy_attribute("__new__extra_args")
        return self.members["__new__extra_args"]
      elif (name == "__init__" and isinstance(val, abstract.Instance) and
            self._has_own(node, val.cls, "__new__")):
        self.load_lazy_attribute("__init__extra_args")
        return self.members["__init__extra_args"]
    return super(Object, self).get_special_attribute(node, name, valself)


class RevealType(abstract.AtomicAbstractValue):
  """For debugging. reveal_type(x) prints the type of "x"."""

  def __init__(self, vm):
    super(RevealType, self).__init__("reveal_type", vm)

  def call(self, node, _, args):
    for a in args.posargs:
      self.vm.errorlog.reveal_type(self.vm.frames, node, a)
    return node, self.vm.convert.build_none(node)


class PropertyTemplate(BuiltinClass):
  """Template for property decorators."""

  _KEYS = ["fget", "fset", "fdel", "doc"]

  def __init__(self, vm, name, module="__builtin__"):  # pylint: disable=useless-super-delegation
    super(PropertyTemplate, self).__init__(vm, name, module)

  def signature(self):
    # Minimal signature, only used for constructing exceptions.
    return function.Signature.from_param_names(self.name, tuple(self._KEYS))

  def _get_args(self, args):
    ret = dict(zip(self._KEYS, args.posargs))
    for k, v in args.namedargs.iteritems():
      if k not in self._KEYS:
        raise function.WrongKeywordArgs(self.signature(), args, self.vm, [k])
      ret[k] = v
    return ret

  def call(self, node, funcv, args):
    raise NotImplementedError()


class PropertyInstance(abstract.SimpleAbstractValue, mixin.HasSlots):
  """Property instance (constructed by Property.call())."""

  CAN_BE_ABSTRACT = True

  def __init__(self, vm, name, cls, fget=None, fset=None, fdel=None, doc=None):
    super(PropertyInstance, self).__init__("property", vm)
    mixin.HasSlots.init_mixin(self)
    self.name = name  # Reports the correct decorator in error messages.
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    self.doc = doc
    self.cls = cls
    self.set_slot("__get__", self.fget_slot)
    self.set_slot("__set__", self.fset_slot)
    self.set_slot("__delete__", self.fdelete_slot)
    self.set_slot("getter", self.getter_slot)
    self.set_slot("setter", self.setter_slot)
    self.set_slot("deleter", self.deleter_slot)
    self.is_abstract = any(self._is_fn_abstract(x) for x in [fget, fset, fdel])

  def _is_fn_abstract(self, func_var):
    if func_var is None:
      return False
    return any(getattr(d, "is_abstract", None) for d in func_var.data)

  def get_class(self):
    return self.cls

  def fget_slot(self, node, obj, objtype):
    return self.vm.call_function(node, self.fget, function.Args((obj,)))

  def fset_slot(self, node, obj, value):
    return self.vm.call_function(
        node, self.fset, function.Args((obj, value)))

  def fdelete_slot(self, node, obj):
    return self.vm.call_function(
        node, self.fdel, function.Args((obj,)))

  def getter_slot(self, node, fget):
    prop = PropertyInstance(
        self.vm, self.name, self.cls, fget, self.fset, self.fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fget.bindings, node)
    return node, result

  def setter_slot(self, node, fset):
    prop = PropertyInstance(
        self.vm, self.name, self.cls, self.fget, fset, self.fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fset.bindings, node)
    return node, result

  def deleter_slot(self, node, fdel):
    prop = PropertyInstance(
        self.vm, self.name, self.cls, self.fget, self.fset, fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fdel.bindings, node)
    return node, result


class Property(PropertyTemplate):
  """Property method decorator."""

  def __init__(self, vm):
    super(Property, self).__init__(vm, "property")

  def call(self, node, funcv, args):
    property_args = self._get_args(args)
    return node, PropertyInstance(
        self.vm, "property", self, **property_args).to_variable(node)


class StaticMethodInstance(abstract.SimpleAbstractValue, mixin.HasSlots):
  """StaticMethod instance (constructed by StaticMethod.call())."""

  def __init__(self, vm, cls, func):
    super(StaticMethodInstance, self).__init__("staticmethod", vm)
    mixin.HasSlots.init_mixin(self)
    self.func = func
    self.cls = cls
    self.set_slot("__get__", self.func_slot)

  def get_class(self):
    return self.cls

  def func_slot(self, node, obj, objtype):
    return node, self.func


class StaticMethod(BuiltinClass):
  """Static method decorator."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature.from_param_names("staticmethod", ("func",))

  def __init__(self, vm):
    super(StaticMethod, self).__init__(vm, "staticmethod")

  def call(self, node, funcv, args):
    if len(args.posargs) != 1:
      raise function.WrongArgCount(self._SIGNATURE, args, self.vm)
    arg = args.posargs[0]
    return node, StaticMethodInstance(self.vm, self, arg).to_variable(node)


class ClassMethodCallable(abstract.BoundFunction):
  """Tag a ClassMethod bound function so we can dispatch on it."""


class ClassMethodInstance(abstract.SimpleAbstractValue, mixin.HasSlots):
  """ClassMethod instance (constructed by ClassMethod.call())."""

  def __init__(self, vm, cls, func):
    super(ClassMethodInstance, self).__init__("classmethod", vm)
    mixin.HasSlots.init_mixin(self)
    self.cls = cls
    self.func = func
    self.set_slot("__get__", self.func_slot)

  def get_class(self):
    return self.cls

  def func_slot(self, node, obj, objtype):
    results = [ClassMethodCallable(objtype, b.data) for b in self.func.bindings]
    return node, self.vm.program.NewVariable(results, [], node)


class ClassMethod(BuiltinClass):
  """Static method decorator."""
  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature.from_param_names("classmethod", ("func",))

  def __init__(self, vm):
    super(ClassMethod, self).__init__(vm, "classmethod")

  def call(self, node, funcv, args):
    if len(args.posargs) != 1:
      raise function.WrongArgCount(self._SIGNATURE, args, self.vm)
    arg = args.posargs[0]
    return node, ClassMethodInstance(self.vm, self, arg).to_variable(node)
