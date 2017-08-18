"""Custom implementations of builtin types."""

from pytype import abstract
from pytype import function


class TypeNew(abstract.PyTDFunction):
  """Implements type.__new__."""

  def call(self, node, func, args):
    if len(args.posargs) == 4:
      self._match_args(node, args)  # May raise FailedFunctionCall.
      cls, name_var, bases_var, class_dict_var = args.posargs
      try:
        bases = list(abstract.get_atomic_python_constant(bases_var))
        if not bases:
          bases = [
              self.vm.convert.object_type.to_variable(self.vm.root_cfg_node)]
        variable = self.vm.make_class(
            node, name_var, bases, class_dict_var, cls)
      except abstract.ConversionError:
        pass
      else:
        return node, variable
    return super(TypeNew, self).call(node, func, args)


class ObjectPredicate(abstract.AtomicAbstractValue):
  """The base class for builtin predicates of the form f(obj, value).

  Subclasses need to override the following:

  _call_predicate(self, node, left, right): The implementation of the predicate.
  """

  def __init__(self, name, vm):
    super(ObjectPredicate, self).__init__(name, vm)
    # Map of True/False/None (where None signals an ambiguous bool) to
    # vm values.
    self._vm_values = {
        True: vm.convert.true,
        False: vm.convert.false,
        None: vm.convert.primitive_class_instances[bool],
    }

  def call(self, node, _, args):
    try:
      func = self.vm.convert.name_to_value("__builtin__.%s" % self.name)
      func._match_args(node, args)  # pylint: disable=protected-access
      node = node.ConnectNew(self.name)
      result = self.vm.program.NewVariable()
      for left in args.posargs[0].bindings:
        for right in args.posargs[1].bindings:
          node, pyval = self._call_predicate(node, left.data, right.data)
          result.AddBinding(self._vm_values[pyval],
                            source_set=(left, right), where=node)
    except abstract.InvalidParameters as ex:
      self.vm.errorlog.invalid_function_call(self.vm.frames, ex)
      result = self.vm.convert.create_new_unsolvable(node)
    return node, result


class HasAttr(ObjectPredicate):
  """The hasattr() function."""

  def __init__(self, vm):
    super(HasAttr, self).__init__("hasattr", vm)

  def _call_predicate(self, node, left, right):
    return self._has_attr(node, left, right)

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
    if (not isinstance(attr, abstract.PythonConstant) or
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
  if isinstance(value, abstract.Class):
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


def _check_against_mro(target, class_spec):
  """Check if any of the classes are in the target's MRO.

  Args:
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
    if c in target.mro:
      return True  # A definite match.
  # No matches, return result depends on whether _flatten() was
  # ambiguous.
  return None if ambiguous else False


class IsInstance(ObjectPredicate):
  """The isinstance() function."""

  def __init__(self, vm):
    super(IsInstance, self).__init__("isinstance", vm)

  def _call_predicate(self, node, left, right):
    return node, self._is_instance(left, right)

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
    if isinstance(obj, abstract.AMBIGUOUS_OR_EMPTY):
      return None
    # Assume a single binding for the object's class variable.  If this isn't
    # the case, treat the call as ambiguous.
    cls_var = obj.get_class()
    if cls_var is None:
      return None
    try:
      obj_class = abstract.get_atomic_value(cls_var)
    except abstract.ConversionError:
      return None
    return _check_against_mro(obj_class, class_spec)


class IsSubclass(ObjectPredicate):
  """The issubclass() function."""

  def __init__(self, vm):
    super(IsSubclass, self).__init__("issubclass", vm)

  def _call_predicate(self, node, left, right):
    return node, self._is_subclass(left, right)

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

    return _check_against_mro(cls, class_spec)


class SuperInstance(abstract.AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.cls = self.vm.convert.super_type.to_variable(vm.root_cfg_node)
    self.super_cls = cls
    self.super_obj = obj
    self.get = abstract.NativeFunction("__get__", self.get, self.vm)
    self.set = abstract.NativeFunction("__set__", self.set, self.vm)

  def get(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def set(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__get__":
      return self.get.to_variable(node)
    elif name == "__set__":
      return self.set.to_variable(node)
    else:
      return super(SuperInstance, self).get_special_attribute(
          node, name, valself)

  def get_class(self):
    return self.cls

  def call(self, node, _, args):
    self.vm.errorlog.not_callable(self.vm.frames, self)
    return node, abstract.Unsolvable(self.vm).to_variable(node)


class Super(abstract.PyTDClass):
  """The super() function. Calling it will create a SuperInstance."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "super", ("cls", "self"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(Super, self).__init__(
        "super", vm.lookup_builtin("__builtin__.super"), vm)
    self.module = "__builtin__"

  def call(self, node, _, args):
    result = self.vm.program.NewVariable()
    num_args = len(args.posargs)
    if 1 <= num_args and num_args <= 2:
      super_objects = args.posargs[1].bindings if num_args == 2 else [None]
      for cls in args.posargs[0].bindings:
        if not isinstance(cls.data, (abstract.Class,
                                     abstract.AMBIGUOUS_OR_EMPTY)):
          bad = abstract.BadParam(
              name="cls", expected=self.vm.convert.type_type)
          raise abstract.WrongArgTypes(
              self._SIGNATURE, args, self.vm, bad_param=bad)
        for obj in super_objects:
          if obj:
            result.AddBinding(
                SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
          else:
            result.AddBinding(
                SuperInstance(cls.data, None, self.vm), [cls], node)
    else:
      raise abstract.WrongArgCount(self._SIGNATURE, args, self.vm)
    return node, result


class Object(abstract.PyTDClass):
  """Implementation of __builtin__.object."""

  def __init__(self, vm):
    super(Object, self).__init__(
        "object", vm.lookup_builtin("__builtin__.object"), vm)
    self.module = "__builtin__"

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
      cls: An abstract.Class.
      method: The method name. So that we don't have to handle the cases when
        the method doesn't exist, we only support "__new__" and "__init__".

    Returns:
      True if the class's definition of the method is different from the
      definition in __builtin__.object, False otherwise.
    """
    assert method in ("__new__", "__init__")
    if not isinstance(cls, abstract.Class):
      return False
    self.load_lazy_attribute(method)
    obj_method = self.members[method]
    _, cls_method = self.vm.attribute_handler.get_class_attribute(
        node, cls, method)
    return obj_method.data != cls_method.data

  def get_special_attribute(self, node, name, valself):
    # Based on the definitions of object_init and object_new in
    # cpython/Objects/typeobject.c (https://goo.gl/bTEBRt). It is legal to pass
    # extra arguments to object.__new__ if the calling class overrides
    # object.__init__, and vice versa.
    if valself:
      val = valself.data
      if name == "__new__" and self._has_own(node, val, "__init__"):
        self.load_lazy_attribute("__new__extra_args")
        return self.members["__new__extra_args"]
      elif (name == "__init__" and isinstance(val, abstract.Instance) and
            any(self._has_own(node, cls, "__new__") for cls in val.cls.data)):
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


class PropertyInstance(abstract.SimpleAbstractValue, abstract.HasSlots):
  """Property instance (constructed by Property.call())."""

  def __init__(self, vm, fget=None, fset=None, fdel=None, doc=None):
    super(PropertyInstance, self).__init__("property", vm)
    abstract.HasSlots.init_mixin(self)
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    self.doc = doc
    self.set_slot("__get__", self.fget_slot)
    self.set_slot("__set__", self.fset_slot)
    self.set_slot("__delete__", self.fdelete_slot)
    self.set_slot("getter", self.getter_slot)
    self.set_slot("setter", self.setter_slot)
    self.set_slot("deleter", self.deleter_slot)

  def fget_slot(self, node, obj, objtype):
    return self.vm.call_function(
        node, self.fget, abstract.FunctionArgs((obj,)))

  def fset_slot(self, node, obj, value):
    return self.vm.call_function(
        node, self.fset, abstract.FunctionArgs((obj, value)))

  def fdelete_slot(self, node, obj):
    return self.vm.call_function(
        node, self.fdel, abstract.FunctionArgs((obj,)))

  def getter_slot(self, node, fget):
    prop = PropertyInstance(self.vm, fget, self.fset, self.fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fget.bindings, node)
    return node, result

  def setter_slot(self, node, fset):
    prop = PropertyInstance(self.vm, self.fget, fset, self.fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fset.bindings, node)
    return node, result

  def deleter_slot(self, node, fdel):
    prop = PropertyInstance(self.vm, self.fget, self.fset, fdel, self.doc)
    result = self.vm.program.NewVariable([prop], fdel.bindings, node)
    return node, result


class Property(abstract.PyTDClass):
  """Property method decorator."""

  _KEYS = ["fget", "fset", "fdel", "doc"]
  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "property", tuple(_KEYS), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(Property, self).__init__(
        "property", vm.lookup_builtin("__builtin__.property"), vm)
    self.module = "__builtin__"

  def _get_args(self, args):
    ret = dict(zip(self._KEYS, args.posargs))
    for k, v in args.namedargs.iteritems():
      if k not in self._KEYS:
        raise abstract.WrongKeywordArgs(self._SIGNATURE, args, self.vm, [k])
      ret[k] = v
    return ret

  def call(self, node, funcv, args):
    property_args = self._get_args(args)
    source_set = [x for arg in property_args.values() for x in arg.bindings]
    result = self.vm.program.NewVariable(
        [PropertyInstance(self.vm, **property_args)],
        source_set=source_set, where=node)
    return node, result


class Abs(abstract.PyTDFunction):
  """Implements abs."""

  def __init__(self, vm):
    f = vm.lookup_builtin("__builtin__.abs")
    signatures = [abstract.PyTDSignature(f.name, sig, vm)
                  for sig in f.signatures]
    super(Abs, self).__init__(f.name, signatures, f.kind, vm)

  def call(self, node, _, args):
    self._match_args(node, args)
    arg = args.posargs[0]
    abs_fn = self.vm.program.NewVariable(source_set=arg.bindings, where=node)
    for b in arg.bindings:
      node, result = self.vm.attribute_handler.get_attribute(
          node, b.data, "__abs__", valself=b)
      abs_fn.PasteVariable(result)
    return self.vm.call_function(node, abs_fn, abstract.FunctionArgs(()))
