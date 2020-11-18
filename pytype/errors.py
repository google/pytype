"""Code and data structures for storing and displaying errors."""

import collections
import contextlib
import csv
import logging
import re
import sys
from typing import Iterable, Optional, Union

from pytype import abstract
from pytype import debug
from pytype import function
from pytype import mixin
from pytype import utils
from pytype.pytd import escape
from pytype.pytd import optimize
from pytype.pytd import pytd_utils
from pytype.pytd import slots
from pytype.pytd import visitors
import six

# Usually we call the logger "log" but that name is used quite often here.
_log = logging.getLogger(__name__)


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2

# The set of known error names.
_ERROR_NAMES = set()

# The current error name, managed by the error_name decorator.
_CURRENT_ERROR_NAME = utils.DynamicVar()

# Max number of calls in the traceback string.
MAX_TRACEBACK_LENGTH = 3

# Max number of tracebacks to show for the same error.
MAX_TRACEBACKS = 3

# Marker indicating the start of a traceback.
TRACEBACK_MARKER = "Called from (traceback):"

# Symbol representing an elided portion of the stack.
_ELLIPSIS = object()


def _error_name(name):
  """Decorate a function so that it binds the current error name."""
  _ERROR_NAMES.add(name)
  def wrap(func):
    def invoke(*args, **kwargs):
      with _CURRENT_ERROR_NAME.bind(name):
        return func(*args, **kwargs)
    return invoke
  return wrap


def _maybe_truncate_traceback(traceback):
  """Truncate the traceback if it is too long.

  Args:
    traceback: A list representing an error's traceback. There should be one
      list item per entry in the traceback (in the right order); beyond that,
      this function does not care about the item types.

  Returns:
    The traceback, possibly with some items removed and an _ELLIPSIS inserted.
    Guaranteed to be no longer than MAX_TRACEBACK_LENGTH.
  """
  if len(traceback) > MAX_TRACEBACK_LENGTH:
    return traceback[:MAX_TRACEBACK_LENGTH-2] + [_ELLIPSIS, traceback[-1]]
  else:
    return traceback


def _make_traceback_str(frames):
  """Turn a stack of frames into a traceback string."""
  if len(frames) < 2 or (
      frames[-1].f_code and not frames[-1].f_code.get_arg_count()):
    # A traceback is usually unnecessary when the topmost frame has no
    # arguments. If this frame ran during module loading, caching prevented it
    # from running again without a traceback, so we drop the traceback manually.
    return None
  frames = frames[:-1]
  frames = _maybe_truncate_traceback(frames)
  traceback = []
  format_line = "line %d, in %s"
  for frame in frames:
    if frame is _ELLIPSIS:
      line = "..."
    elif frame.current_opcode.code.co_name == "<module>":
      line = format_line % (frame.current_opcode.line, "current file")
    else:
      line = format_line % (frame.current_opcode.line,
                            frame.current_opcode.code.co_name)
    traceback.append(line)
  return TRACEBACK_MARKER + "\n  " + "\n  ".join(traceback)


def _dedup_opcodes(stack):
  """Dedup the opcodes in a stack of frames."""
  deduped_stack = []
  for frame in stack:
    if frame.current_opcode and (
        not deduped_stack or
        frame.current_opcode.line != deduped_stack[-1].current_opcode.line):
      # We can have consecutive opcodes with the same line number due to, e.g.,
      # a set comprehension. The first opcode we encounter is the one with the
      # real method name, whereas the second's method name is something like
      # <setcomp>, so we keep the first.
      deduped_stack.append(frame)
  return deduped_stack


def _compare_traceback_strings(left, right):
  """Try to compare two traceback strings.

  Two traceback strings are comparable if they are equal, or if one ends with
  the other. For example, these two tracebacks are comparable:
    Traceback:
      line 1, in <module>
      line 2, in foo
    Traceback:
      line 2, in foo
  and the first is greater than the second.

  Args:
    left: A string or None.
    right: A string or None.

  Returns:
    None if the inputs aren't comparable, else an integer.
  """
  if left == right:
    return 0
  left = left[len(TRACEBACK_MARKER):] if left else ""
  right = right[len(TRACEBACK_MARKER):] if right else ""
  if left.endswith(right):
    return 1
  elif right.endswith(left):
    return -1
  else:
    return None


def _function_name(name, capitalize=False):
  builtin_prefix = "__builtin__."
  if name.startswith(builtin_prefix):
    ret = "built-in function %s" % name[len(builtin_prefix):]
  else:
    ret = "function %s" % name
  if capitalize:
    return ret[0].upper() + ret[1:]
  else:
    return ret


class CheckPoint:
  """Represents a position in an error log."""

  def __init__(self, errors):
    self._errorlog_errors = errors
    self._position = len(errors)
    self.errors = None

  def revert(self):
    self.errors = self._errorlog_errors[self._position:]
    self._errorlog_errors[:] = self._errorlog_errors[:self._position]


class Error:
  """Representation of an error in the error log.

  Attributes:
    name: The error name.
    bad_call: Optionally, a `pytype.function.BadCall` of details of a bad
              function call.
    details: Optionally, a string of message details.
    filename: The file in which the error occurred.
    lineno: The line number at which the error occurred.
    message: The error message string.
    methodname: The method in which the error occurred.
    severity: The error level (error or warning), an integer.
    keyword: Optionally, the culprit keyword in the line where error is.
             e.g.,
             message = "No attribute '_submatch' on BasePattern"
             keyword = _submatch
    keyword_context: Optionally, a string naming the object on which `keyword`
                     occurs. e.g. the fully qualified module name that a
                     non-existent function doesn't exist on.
    traceback: Optionally, an error traceback.
  """

  def __init__(self, severity, message, filename=None, lineno=0,
               methodname=None, details=None, traceback=None, keyword=None,
               keyword_context=None, bad_call=None):
    name = _CURRENT_ERROR_NAME.get()
    assert name, ("Errors must be created from a caller annotated "
                  "with @error_name.")
    # Required for every Error.
    self._severity = severity
    self._message = message
    self._name = name
    # Optional information about the error.
    self._details = details
    # Optional information about error position.
    self._filename = filename
    self._lineno = lineno or 0
    self._methodname = methodname
    self._traceback = traceback
    self._keyword_context = keyword_context
    self._keyword = keyword
    self._bad_call = bad_call

  @classmethod
  def with_stack(cls, stack, severity, message, **kwargs):
    """Return an error using a stack for position information.

    Args:
      stack: A list of state.Frame or state.SimpleFrame objects.
      severity: The error level (error or warning), an integer.
      message: The error message string.
      **kwargs: Additional keyword args to pass onto the class ctor.

    Returns:
      An Error object.
    """
    stack = _dedup_opcodes(stack) if stack else None
    opcode = stack[-1].current_opcode if stack else None
    if opcode is None:
      return cls(severity, message, **kwargs)
    else:
      return cls(severity, message, filename=opcode.code.co_filename,
                 lineno=opcode.line, methodname=opcode.code.co_name,
                 traceback=_make_traceback_str(stack), **kwargs)

  @classmethod
  def for_test(cls, severity, message, name, **kwargs):
    """Create an _Error with the specified name, for use in tests."""
    with _CURRENT_ERROR_NAME.bind(name):
      return cls(severity, message, **kwargs)

  @property
  def name(self):
    return self._name

  @property
  def lineno(self):
    return self._lineno

  @property
  def filename(self):
    return self._filename

  @property
  def message(self):
    message = self._message
    if self._details:
      message += "\n" + self._details
    if self._traceback:
      message += "\n" + self._traceback
    return message

  @property
  def traceback(self):
    return self._traceback

  @property
  def methodname(self):
    return self._methodname

  @property
  def bad_call(self):
    return self._bad_call

  @property
  def details(self):
    return self._details

  @property
  def keyword(self):
    return self._keyword

  @property
  def keyword_context(self):
    return self._keyword_context

  def _position(self):
    """Return human-readable filename + line number."""
    method = ", in %s" % self._methodname if self._methodname else ""

    if self._filename:
      return "File \"%s\", line %d%s" % (self._filename,
                                         self._lineno,
                                         method)
    elif self._lineno:
      return "Line %d%s" % (self._lineno, method)
    else:
      return ""

  def __str__(self):
    pos = self._position()
    if pos:
      pos += ": "
    text = "%s%s [%s]" % (pos, self._message.replace("\n", "\n  "), self._name)
    if self._details:
      text += "\n  " + self._details.replace("\n", "\n  ")
    if self._traceback:
      text += "\n" + self._traceback
    return text

  def drop_traceback(self):
    with _CURRENT_ERROR_NAME.bind(self._name):
      return self.__class__(
          severity=self._severity,
          message=self._message,
          filename=self._filename,
          lineno=self._lineno,
          methodname=self._methodname,
          details=self._details,
          keyword=self._keyword,
          traceback=None)


class ErrorLogBase:
  """A stream of errors."""

  def __init__(self):
    self._errors = []
    # An error filter (initially None)
    self._filter = None

  def __len__(self):
    return len(self._errors)

  def __iter__(self):
    return iter(self._errors)

  def __getitem__(self, index):
    return self._errors[index]

  def copy_from(self, errors, stack):
    for e in errors:
      with _CURRENT_ERROR_NAME.bind(e.name):
        self.error(stack, e.message, e.details, e.keyword, e.bad_call,
                   e.keyword_context)

  def is_valid_error_name(self, name):
    """Return True iff name was defined in an @error_name() decorator."""
    return name in _ERROR_NAMES

  def set_error_filter(self, filt):
    """Set the error filter.

    Args:
      filt: A function or callable object that accepts a single argument of
          type Error and returns True if that error should be included in the
          log.  A filter of None will add all errors.
    """
    self._filter = filt

  def has_error(self):
    """Return true iff an Error with SEVERITY_ERROR is present."""
    # pylint: disable=protected-access
    return any(e._severity == SEVERITY_ERROR for e in self._errors)

  def _add(self, error):
    if self._filter is None or self._filter(error):
      _log.info("Added error to log: %s\n%s", error.name, error)
      if _log.isEnabledFor(logging.DEBUG):
        _log.debug(debug.stack_trace(limit=1).rstrip())
      self._errors.append(error)

  def warn(self, stack, message, *args):
    self._add(Error.with_stack(stack, SEVERITY_WARNING, message % args))

  def error(self, stack, message, details=None, keyword=None, bad_call=None,
            keyword_context=None):
    self._add(Error.with_stack(stack, SEVERITY_ERROR, message, details=details,
                               keyword=keyword, bad_call=bad_call,
                               keyword_context=keyword_context))

  @contextlib.contextmanager
  def checkpoint(self):
    """Record errors without adding them to the errorlog."""
    _log.info("Checkpointing errorlog at %d errors", len(self._errors))
    checkpoint = CheckPoint(self._errors)
    try:
      yield checkpoint
    finally:
      checkpoint.revert()
    _log.info("Restored errorlog to checkpoint: %d errors reverted",
              len(checkpoint.errors))

  def print_to_csv_file(self, filename, open_function=open):
    """Print the errorlog to a csv file."""
    with open_function(filename, "w") as f:
      csv_file = csv.writer(f, delimiter=",")
      for error in self.unique_sorted_errors():
        # pylint: disable=protected-access
        # TODO(b/159038861): Add _methodname
        if error._details and error._traceback:
          details = error._details + "\n\n" + error._traceback
        elif error._traceback:
          details = error._traceback
        else:
          details = error._details
        csv_file.writerow(
            [error._filename,
             error._lineno,
             error._name,
             error._message,
             details])

  def print_to_file(self, fi):
    for error in self.unique_sorted_errors():
      print(error, file=fi)

  def unique_sorted_errors(self):
    """Gets the unique errors in this log, sorted on filename and lineno."""
    unique_errors = collections.OrderedDict()
    for error in self._sorted_errors():
      error_without_traceback = str(error.drop_traceback())
      if error_without_traceback not in unique_errors:
        unique_errors[error_without_traceback] = [error]
        continue
      errors = unique_errors[error_without_traceback]
      for previous_error in list(errors):  # make a copy, since we modify errors
        traceback_cmp = _compare_traceback_strings(error.traceback,
                                                   previous_error.traceback)
        if traceback_cmp is None:
          # We have multiple bad call sites, e.g.,
          #   def f(x):  x + 42
          #   f("hello")  # error
          #   f("world")  # same error, different backtrace
          # so we'll report this error multiple times with different backtraces.
          continue
        elif traceback_cmp < 0:
          # If the current traceback is shorter, use the current error instead
          # of the previous one.
          errors.remove(previous_error)
        else:
          # One of the previous errors has a shorter traceback than the current
          # one, so the latter can be discarded.
          break
      else:
        if len(errors) < MAX_TRACEBACKS:
          errors.append(error)
    return sum(unique_errors.values(), [])

  def _sorted_errors(self):
    return sorted(self._errors, key=lambda x: (x.filename or "", x.lineno))

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)

  def __str__(self):
    io = six.StringIO()
    self.print_to_file(io)
    return io.getvalue()


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  def _pytd_print(self, pytd_type):
    """Print the name of the pytd type."""
    name = pytd_utils.Print(pytd_utils.CanonicalOrdering(optimize.Optimize(
        pytd_type.Visit(visitors.RemoveUnknownClasses()))))
    # Clean up autogenerated namedtuple names, e.g. "namedtuple-X-a-_0-c"
    # becomes just "X", by extracting out just the type name.
    if "namedtuple" in name:
      return escape.unpack_namedtuple(name)
    nested_class_match = re.search(r"_(?:\w+)_DOT_", name)
    if nested_class_match:
      # Pytype doesn't have true support for nested classes. Instead, for
      #   class Foo:
      #     class Bar: ...
      # it outputs:
      #   class _Foo_DOT_Bar: ...
      #   class Foo:
      #     Bar = ...  # type: Type[_Foo_DOT_Bar]
      # Replace _Foo_DOT_Bar with Foo.Bar in error messages for readability.
      # TODO(b/35138984): Get rid of this hack.
      start = nested_class_match.start()
      return name[:start] + name[start+1:].replace("_DOT_", ".")
    return name

  def _print_as_expected_type(self, t, instance=None):
    """Print abstract value t as a pytd type."""
    if t.is_late_annotation():
      return t.expr
    elif isinstance(t, (abstract.Unknown, abstract.Unsolvable, mixin.Class,
                        abstract.Union)):
      with t.vm.convert.pytd_convert.set_output_mode(
          t.vm.convert.pytd_convert.OutputMode.DETAILED):
        return self._pytd_print(t.get_instance_type(instance=instance))
    elif (isinstance(t, mixin.PythonConstant) and
          not getattr(t, "could_contain_anything", False)):
      return re.sub(r"(\\n|\s)+", " ",
                    t.str_of_constant(self._print_as_expected_type))
    elif isinstance(t, abstract.AnnotationClass) or not t.cls:
      return t.name
    else:
      return "<instance of %s>" % self._print_as_expected_type(t.cls, t)

  def _print_as_actual_type(self, t, literal=False):
    if literal:
      output_mode = t.vm.convert.pytd_convert.OutputMode.LITERAL
    else:
      output_mode = t.vm.convert.pytd_convert.OutputMode.DETAILED
    with t.vm.convert.pytd_convert.set_output_mode(output_mode):
      return self._pytd_print(t.to_type())

  def _print_as_generic_type(self, t):
    generic = pytd_utils.MakeClassOrContainerType(
        t.get_instance_type().base_type,
        t.formal_type_parameters.keys(),
        False)
    with t.vm.convert.pytd_convert.set_output_mode(
        t.vm.convert.pytd_convert.OutputMode.DETAILED):
      return self._pytd_print(generic)

  def _print_as_return_types(self, node, formal, actual, bad):
    """Print the actual and expected values for a return type."""
    convert = formal.vm.convert.pytd_convert
    with convert.set_output_mode(convert.OutputMode.DETAILED):
      expected = self._pytd_print(formal.get_instance_type(node))
    if "Literal[" in expected:
      output_mode = convert.OutputMode.LITERAL
    else:
      output_mode = convert.OutputMode.DETAILED
    with convert.set_output_mode(output_mode):
      actual = self._pytd_print(pytd_utils.JoinTypes(
          view[actual].data.to_type(node, view=view) for view in bad))
    # typing.NoReturn is a prettier alias for nothing.
    fmt = lambda ret: "NoReturn" if ret == "nothing" else ret
    return fmt(expected), fmt(actual)

  def _join_printed_types(self, types):
    """Pretty-print the union of the printed types."""
    types = sorted(set(types))  # dedup
    if len(types) == 1:
      return next(iter(types))
    elif types:
      if "None" in types:
        types.remove("None")
        return "Optional[%s]" % self._join_printed_types(types)
      else:
        return "Union[%s]" % ", ".join(types)
    else:
      return "nothing"

  def _iter_sig(self, sig):
    """Iterate through a function.Signature object. Focus on a bad parameter."""
    for name in sig.param_names:
      yield "", name
    if sig.varargs_name is not None:
      yield "*", sig.varargs_name
    elif sig.kwonly_params:
      yield ("*", "")
    for name in sorted(sig.kwonly_params):
      yield "", name
    if sig.kwargs_name is not None:
      yield "**", sig.kwargs_name

  def _iter_expected(self, sig, bad_param):
    """Yield the prefix, name and type information for expected parameters."""
    for prefix, name in self._iter_sig(sig):
      suffix = " = ..." if name in sig.defaults else ""
      if bad_param and name == bad_param.name:
        type_str = self._print_as_expected_type(bad_param.expected)
        suffix = ": " + type_str + suffix
      yield prefix, name, suffix

  def _iter_actual(self, sig, passed_args, bad_param, literal):
    """Yield the prefix, name and type information for actual parameters."""
    # We want to display the passed_args in the order they're defined in the
    # signature, unless there are starargs or starstarargs.
    # Map param names to their position in the list, then sort the list of
    # passed args so it's in the same order as the params.
    keys = {param: n for n, (_, param) in enumerate(self._iter_sig(sig))}
    def key_f(arg):
      arg_name = arg[0]
      # starargs are given anonymous names, which won't be found in the sig.
      # Instead, use the same name as the varags param itself, if present.
      if arg_name not in keys and pytd_utils.ANON_PARAM.match(arg_name):
        return keys.get(sig.varargs_name, len(keys)+1)
      return keys.get(arg_name, len(keys)+1)
    for name, arg in sorted(passed_args, key=key_f):
      if bad_param and name == bad_param.name:
        suffix = ": " + self._print_as_actual_type(arg, literal=literal)
      else:
        suffix = ""
      yield "", name, suffix

  def _print_args(self, arg_iter, bad_param):
    """Pretty-print a list of arguments. Focus on a bad parameter."""
    # (foo, bar, broken : type, ...)
    printed_params = []
    found = False
    for prefix, name, suffix in arg_iter:
      if bad_param and name == bad_param.name:
        printed_params.append(prefix + name + suffix)
        found = True
      elif found:
        printed_params.append("...")
        break
      elif pytd_utils.ANON_PARAM.match(name):
        printed_params.append(prefix + "_")
      else:
        printed_params.append(prefix + name)
    return ", ".join(printed_params)

  @_error_name("pyi-error")
  def pyi_error(self, stack, name, error):
    self.error(stack, "Couldn't import pyi for %r" % name, str(error),
               keyword=name)

  @_error_name("attribute-error")
  def _attribute_error(self, stack, binding, attr_name):
    """Log an attribute error."""
    obj_repr = self._print_as_actual_type(binding.data)
    if len(binding.variable.bindings) > 1:
      # Joining the printed types rather than merging them before printing
      # ensures that we print all of the options when 'Any' is among them.
      details = "In %s" % self._join_printed_types(
          self._print_as_actual_type(v) for v in binding.variable.data)
    else:
      details = None
    self.error(
        stack, "No attribute %r on %s" % (attr_name, obj_repr), details=details,
        keyword=attr_name)

  @_error_name("not-writable")
  def not_writable(self, stack, obj, attr_name):
    obj_values = obj.vm.merge_values([obj])
    obj_repr = self._print_as_actual_type(obj_values)
    self.error(stack, "Can't assign attribute %r on %s" % (attr_name, obj_repr),
               keyword=attr_name, keyword_context=obj_repr)

  @_error_name("module-attr")
  def _module_attr(self, stack, binding, attr_name):
    module_name = binding.data.name
    self.error(stack, "No attribute %r on module %r" % (attr_name, module_name),
               keyword=attr_name, keyword_context=module_name)

  def attribute_error(self, stack, binding, attr_name):
    if attr_name in slots.SYMBOL_MAPPING:
      obj = self._print_as_actual_type(binding.data)
      details = "No attribute %r on %s" % (attr_name, obj)
      self._unsupported_operands(stack, attr_name, obj, details=details)
    elif isinstance(binding.data, abstract.Module):
      self._module_attr(stack, binding, attr_name)
    else:
      self._attribute_error(stack, binding, attr_name)

  @_error_name("unbound-type-param")
  def unbound_type_param(self, stack, obj, attr_name, type_param_name):
    self.error(
        stack, "Can't access attribute %r on %s" % (attr_name, obj.name),
        "No binding for type parameter %s" % type_param_name, keyword=attr_name,
        keyword_context=obj.name)

  @_error_name("name-error")
  def name_error(self, stack, name):
    self.error(stack, "Name %r is not defined" % name, keyword=name)

  @_error_name("import-error")
  def import_error(self, stack, module_name):
    self.error(stack, "Can't find module %r." % module_name,
               keyword=module_name)

  def _explain_protocol_mismatch(self, protocol_param, passed_params):
    """Return possibly extra protocol details about an argument mismatch."""
    if not protocol_param:
      return []
    expected = protocol_param.expected
    vm = expected.vm
    if not isinstance(expected, mixin.Class) or not expected.is_protocol:
      return []
    p = None  # make pylint happy
    for name, p in passed_params:
      if name == protocol_param.name:
        break
    else:
      return []
    methods = vm.matcher.unimplemented_protocol_methods(p, expected)
    if not methods:
      # Happens if all the protocol methods are implemented, but with the wrong
      # types. We don't yet provide more detail about that.
      return []
    return [
        "\nThe following methods aren't implemented on %s:\n" %
        self._print_as_actual_type(p)] + [", ".join(sorted(methods))]

  def _invalid_parameters(self, stack, message, bad_call):
    """Log an invalid parameters error."""
    sig, passed_args, bad_param = bad_call
    expected = self._print_args(self._iter_expected(sig, bad_param), bad_param)
    literal = "Literal[" in expected
    actual = self._print_args(
        self._iter_actual(sig, passed_args, bad_param, literal), bad_param)
    details = [
        "       Expected: (", expected, ")\n",
        "Actually passed: (", actual,
        ")"]
    details += self._explain_protocol_mismatch(bad_param, passed_args)
    self.error(stack, message, "".join(details), bad_call=bad_call)

  @_error_name("wrong-arg-count")
  def wrong_arg_count(self, stack, name, bad_call):
    message = "%s expects %d arg(s), got %d" % (
        _function_name(name, capitalize=True),
        bad_call.sig.mandatory_param_count(),
        len(bad_call.passed_args))
    self._invalid_parameters(stack, message, bad_call)

  def _get_binary_operation(self, function_name, bad_call):
    """Return (op, left, right) if the function should be treated as a binop."""
    maybe_left_operand, _, f = function_name.rpartition(".")
    # Check that
    # (1) the function is bound to an object (the left operand),
    # (2) the function has a pretty representation,
    # (3) either there are exactly two passed args or the function is one we've
    #     chosen to treat as a binary operation.
    if (not maybe_left_operand or f not in slots.SYMBOL_MAPPING or
        (len(bad_call.passed_args) != 2 and
         f not in ("__setitem__", "__getslice__"))):
      return None
    for arg_name, arg_value in bad_call.passed_args[1:]:
      if arg_name == bad_call.bad_param.name:
        # maybe_left_operand is something like `dict`, but we want a more
        # precise type like `Dict[str, int]`.
        left_operand = self._print_as_actual_type(bad_call.passed_args[0][1])
        right_operand = self._print_as_actual_type(arg_value)
        return f, left_operand, right_operand
    return None

  def wrong_arg_types(self, stack, name, bad_call):
    """Log [wrong-arg-types]."""
    operation = self._get_binary_operation(name, bad_call)
    if operation:
      operator, left_operand, right_operand = operation
      operator_name = _function_name(operator, capitalize=True)
      expected_right_operand = self._print_as_expected_type(
          bad_call.bad_param.expected)
      details = "%s on %s expects %s" % (
          operator_name, left_operand, expected_right_operand)
      self._unsupported_operands(
          stack, operator, left_operand, right_operand, details=details)
    else:
      self._wrong_arg_types(stack, name, bad_call)

  @_error_name("wrong-arg-types")
  def _wrong_arg_types(self, stack, name, bad_call):
    """A function was called with the wrong parameter types."""
    message = ("%s was called with the wrong arguments" %
               _function_name(name, capitalize=True))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("wrong-keyword-args")
  def wrong_keyword_args(self, stack, name, bad_call, extra_keywords):
    """A function was called with extra keywords."""
    if len(extra_keywords) == 1:
      message = "Invalid keyword argument %s to %s" % (
          extra_keywords[0], _function_name(name))
    else:
      message = "Invalid keyword arguments %s to %s" % (
          "(" + ", ".join(sorted(extra_keywords)) + ")",
          _function_name(name))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("missing-parameter")
  def missing_parameter(self, stack, name, bad_call, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter %r in call to %s" % (
        missing_parameter, _function_name(name))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("not-callable")
  def not_callable(self, stack, func):
    """Calling an object that isn't callable."""
    if isinstance(func, abstract.InterpreterFunction) and func.is_overload:
      prefix = "@typing.overload-decorated "
    else:
      prefix = ""
    message = "%s%r object is not callable" % (prefix, func.name)
    self.error(stack, message, keyword=func.name)

  @_error_name("not-indexable")
  def not_indexable(self, stack, name, generic_warning=False):
    message = "class %s is not indexable" % name
    if generic_warning:
      self.error(stack, message, "(%r does not subclass Generic)" % name,
                 keyword=name)
    else:
      self.error(stack, message, keyword=name)

  @_error_name("not-instantiable")
  def not_instantiable(self, stack, cls):
    """Instantiating an abstract class."""
    message = "Can't instantiate %s with abstract methods %s" % (
        cls.full_name, ", ".join(sorted(cls.abstract_methods)))
    self.error(stack, message)

  @_error_name("ignored-abstractmethod")
  def ignored_abstractmethod(self, stack, cls_name, method_name):
    message = "Stray abc.abstractmethod decorator on method %s" % method_name
    self.error(stack, message,
               details="(%s does not have metaclass abc.ABCMeta)" % cls_name)

  @_error_name("ignored-metaclass")
  def ignored_metaclass(self, stack, cls, metaclass):
    message = "Metaclass %s on class %s ignored in Python 3" % (metaclass, cls)
    self.error(stack, message)

  @_error_name("duplicate-keyword-argument")
  def duplicate_keyword(self, stack, name, bad_call, duplicate):
    message = ("%s got multiple values for keyword argument %r" %
               (_function_name(name), duplicate))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("invalid-super-call")
  def invalid_super_call(self, stack, message, details=None):
    self.error(stack, message, details)

  def invalid_function_call(self, stack, error):
    """Log an invalid function call."""
    if isinstance(error, function.WrongArgCount):
      self.wrong_arg_count(stack, error.name, error.bad_call)
    elif isinstance(error, function.WrongArgTypes):
      self.wrong_arg_types(stack, error.name, error.bad_call)
    elif isinstance(error, function.WrongKeywordArgs):
      self.wrong_keyword_args(
          stack, error.name, error.bad_call, error.extra_keywords)
    elif isinstance(error, function.MissingParameter):
      self.missing_parameter(
          stack, error.name, error.bad_call, error.missing_parameter)
    elif isinstance(error, function.NotCallable):
      self.not_callable(stack, error.obj)
    elif isinstance(error, function.DuplicateKeyword):
      self.duplicate_keyword(
          stack, error.name, error.bad_call, error.duplicate)
    elif isinstance(error, function.UndefinedParameterError):
      self.name_error(stack, error.name)
    else:
      raise AssertionError(error)

  @_error_name("base-class-error")
  def base_class_error(self, stack, base_var):
    base_cls = self._join_printed_types(
        self._print_as_expected_type(t) for t in base_var.data)
    self.error(stack, "Invalid base class: %s" % base_cls, keyword=base_cls)

  @_error_name("bad-return-type")
  def bad_return_type(self, stack, node, formal, actual, bad):
    expected, actual = self._print_as_return_types(node, formal, actual, bad)
    details = "".join(["         Expected: ", expected, "\n",
                       "Actually returned: ", actual])
    self.error(stack, "bad option in return type", details)

  @_error_name("bad-concrete-type")
  def bad_concrete_type(self, stack, node, formal, actual, bad):
    expected, actual = self._print_as_return_types(node, formal, actual, bad)
    details = "".join(["       Expected: ", expected, "\n",
                       "Actually passed: ", actual])
    self.error(stack, "Invalid instantiation of generic class", details)

  def unsupported_operands(self, stack, operator, var1, var2):
    left = self._join_printed_types(
        self._print_as_actual_type(t) for t in var1.data)
    right = self._join_printed_types(
        self._print_as_actual_type(t) for t in var2.data)
    details = "No attribute %r on %s" % (operator, left)
    if operator in slots.REVERSE_NAME_MAPPING:
      details += " or %r on %s" % (slots.REVERSE_NAME_MAPPING[operator], right)
    self._unsupported_operands(stack, operator, left, right, details=details)

  @_error_name("unsupported-operands")
  def _unsupported_operands(self, stack, operator, *operands, **details):
    # TODO(b/114124544): Change the signature to (..., *operands, details=None)
    assert set(details) <= {"details"}
    self.error(
        stack, "unsupported operand type(s) for %s: %s" % (
            slots.SYMBOL_MAPPING[operator],
            " and ".join(repr(operand) for operand in operands)),
        details=details.get("details"))

  def invalid_annotation(
      self, stack, annot: Optional[Union[str, abstract.AtomicAbstractValue]],
      details=None, name=None):
    if isinstance(annot, abstract.AtomicAbstractValue):
      annot = self._print_as_expected_type(annot)
    self._invalid_annotation(stack, annot, details, name)

  def invalid_ellipses(self, stack, indices, container_name):
    if indices:
      details = "Not allowed at %s %s in %s" % (
          "index" if len(indices) == 1 else "indices",
          ", ".join(str(i) for i in sorted(indices)),
          container_name)
      self._invalid_annotation(stack, "Ellipsis", details, None)

  def ambiguous_annotation(
      self, stack,
      options: Optional[Union[str, Iterable[abstract.AtomicAbstractValue]]],
      name=None):
    if isinstance(options, (str, type(None))):
      desc = options
    else:
      desc = " or ".join(
          sorted(self._print_as_expected_type(o) for o in options))
    self._invalid_annotation(stack, desc, "Must be constant", name)

  @_error_name("invalid-annotation")
  def _invalid_annotation(self, stack, annot_string, details, name):
    """Log the invalid annotation."""
    if name is None:
      suffix = ""
    else:
      suffix = "for " + name
    annot_string = "%r " % annot_string if annot_string else ""
    self.error(stack, "Invalid type annotation %s%s" % (annot_string, suffix),
               details=details)

  @_error_name("mro-error")
  def mro_error(self, stack, name, mro_seqs, details=None):
    seqs = []
    for seq in mro_seqs:
      seqs.append("[%s]" % ", ".join(cls.name for cls in seq))
    suffix = ": %s" % ", ".join(seqs) if seqs else ""
    msg = "%s has invalid inheritance%s." % (name, suffix)
    self.error(stack, msg, keyword=name, details=details)

  @_error_name("invalid-directive")
  def invalid_directive(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_WARNING, message, filename=filename, lineno=lineno))

  @_error_name("late-directive")
  def late_directive(self, filename, lineno, name):
    message = "%s disabled from here to the end of the file" % name
    details = ("Consider limiting this directive's scope or moving it to the "
               "top of the file.")
    self._add(Error(SEVERITY_WARNING, message, details=details,
                    filename=filename, lineno=lineno))

  @_error_name("not-supported-yet")
  def not_supported_yet(self, stack, feature, details=None):
    self.error(stack, "%s not supported yet" % feature, details=details)

  @_error_name("key-error")
  def key_error(self, stack, key):
    self.error(stack, "Key %r possibly not in dictionary (yet)" % key,
               keyword=key)

  @_error_name("python-compiler-error")
  def python_compiler_error(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_ERROR, message, filename=filename, lineno=lineno))

  @_error_name("recursion-error")
  def recursion_error(self, stack, name):
    self.error(stack, "Detected recursion in %s" % name, keyword=name)

  @_error_name("redundant-function-type-comment")
  def redundant_function_type_comment(self, filename, lineno):
    self._add(Error(
        SEVERITY_ERROR,
        "Function type comments cannot be used with annotations",
        filename=filename, lineno=lineno))

  @_error_name("invalid-function-type-comment")
  def invalid_function_type_comment(self, stack, comment, details=None):
    self.error(stack, "Invalid function type comment: %s" % comment,
               details=details)

  @_error_name("ignored-type-comment")
  def ignored_type_comment(self, filename, lineno, comment):
    self._add(Error(
        SEVERITY_WARNING, "Stray type comment: %s" % comment,
        filename=filename, lineno=lineno))

  @_error_name("invalid-typevar")
  def invalid_typevar(self, stack, comment, bad_call=None):
    if bad_call:
      self._invalid_parameters(stack, comment, bad_call)
    else:
      self.error(stack, "Invalid TypeVar: %s" % comment)

  @_error_name("invalid-namedtuple-arg")
  def invalid_namedtuple_arg(self, stack, badname=None, err_msg=None):
    if err_msg is None:
      msg = ("collections.namedtuple argument %r is not a valid typename or "
             "field name.")
      self.warn(stack, msg % badname)
    else:
      self.error(stack, err_msg)

  @_error_name("bad-function-defaults")
  def bad_function_defaults(self, stack, func_name):
    msg = "Attempt to set %s.__defaults__ to a non-tuple value."
    self.warn(stack, msg % func_name)

  @_error_name("bad-slots")
  def bad_slots(self, stack, msg):
    self.error(stack, msg)

  @_error_name("bad-unpacking")
  def bad_unpacking(self, stack, num_vals, num_vars):
    prettify = lambda v, label: "%d %s%s" % (v, label, "" if v == 1 else "s")
    vals_str = prettify(num_vals, "value")
    vars_str = prettify(num_vars, "variable")
    msg = "Cannot unpack %s into %s" % (vals_str, vars_str)
    self.error(stack, msg, keyword=vals_str)

  @_error_name("reveal-type")
  def reveal_type(self, stack, node, var):
    types = [self._print_as_actual_type(b.data)
             for b in var.bindings
             if node.HasCombination([b])]
    self.error(stack, self._join_printed_types(types))

  @_error_name("annotation-type-mismatch")
  def annotation_type_mismatch(self, stack, annot, binding, name):
    """Invalid combination of annotation and assignment."""
    if annot is None:
      return
    annot_string = self._print_as_expected_type(annot)
    literal = "Literal[" in annot_string
    actual_string = self._print_as_actual_type(binding.data, literal=literal)
    details = ("Annotation: %s\n" % annot_string +
               "Assignment: %s" % actual_string)
    if len(binding.variable.bindings) > 1:
      # Joining the printed types rather than merging them before printing
      # ensures that we print all of the options when 'Any' is among them.
      # We don't need to print this if there is only 1 unique type.
      print_types = set(self._print_as_actual_type(v, literal=literal)
                        for v in binding.variable.data)
      if len(print_types) > 1:
        details += "\nIn assignment of type: %s" % self._join_printed_types(
            print_types)
    suffix = "" if name is None else " for " + name
    err_msg = "Type annotation%s does not match type of assignment" % suffix
    self.error(stack, err_msg, details=details)

  @_error_name("container-type-mismatch")
  def container_type_mismatch(self, stack, obj, mutations, name):
    """Invalid combination of annotation and mutation.

    Args:
      stack: the frame stack
      obj: the container instance being mutated
      mutations: a dict of {parameter name: (annotated types, new types)}
      name: the variable name (or None)
    """
    cls = obj.cls
    annot_string = "%s (type parameters %s)" % (
        self._print_as_expected_type(cls),
        self._print_as_generic_type(cls))
    details = "Annotation: %s\n" % annot_string
    contained = ""
    new_contained = ""
    for formal in cls.formal_type_parameters.keys():
      if formal in mutations:
        params, values, _ = mutations[formal]
        old_content = self._join_printed_types(
            set(self._print_as_actual_type(v) for v in params.data))
        new_content = self._join_printed_types(
            set(self._print_as_actual_type(v) for v in values.data))
        contained += "  %s: %s\n" % (formal, old_content)
        new_contained += "  %s: %s\n" % (formal, new_content)
    details += ("Contained types:\n" + contained +
                "New contained types:\n" + new_contained)
    suffix = "" if name is None else " for " + name
    err_msg = "New container type%s does not match type annotation" % suffix
    self.error(stack, err_msg, details=details)

  @_error_name("invalid-function-definition")
  def invalid_function_definition(self, stack, msg):
    """Invalid function constructed via metaprogramming."""
    self.error(stack, msg)


def get_error_names_set():
  return _ERROR_NAMES
