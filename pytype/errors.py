"""Code and data structures for storing and displaying errors."""

import os
import re
import StringIO
import sys


from pytype import abstract
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2

# The set of known error names.
_ERROR_NAMES = set()

# The current error name, managed by the error_name decorator.
_CURRENT_ERROR_NAME = utils.DynamicVar()


def _error_name(name):
  """Decorate a function so that it binds the current error name."""
  _ERROR_NAMES.add(name)
  def wrap(func):
    def invoke(*args, **kwargs):
      with _CURRENT_ERROR_NAME.bind(name):
        return func(*args, **kwargs)
    return invoke
  return wrap


class CheckPoint(object):
  """Represents a position in an error log."""

  def __init__(self, log, position):
    self.log = log
    self.position = position


class Error(object):
  """Representation of an error in the error log."""

  def __init__(self, severity, message, filename=None, lineno=0, column=None,
               linetext=None, methodname=None, details=None):
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
    # TODO(dbaum): Do not allow filename (and maybe lineno) of None.
    self._filename = filename
    self._lineno = lineno or 0
    self._column = column
    self._linetext = linetext
    self._methodname = methodname

  @classmethod
  def from_csv_row(cls, row):
    """Translate a CSV row back into an Error object."""

    filename, lineno, name, message = row

    with _CURRENT_ERROR_NAME.bind(name):
      return cls(SEVERITY_ERROR, message,
                 lineno=int(lineno),
                 filename=filename)

  @classmethod
  def at_opcode(cls, opcode, severity, message, details=None):
    """Return an error using an opcode for position information."""
    if opcode is None:
      return cls(severity, message, details=details)
    else:
      return cls(severity, message, filename=opcode.code.co_filename,
                 lineno=opcode.line, methodname=opcode.code.co_name,
                 details=details)

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
    if self._details is None:
      return self._message
    else:
      return self._message + "\n" + self._details

  def _position(self):
    """Return human-readable filename + line number."""
    method = ", in %s" % self._methodname if self._methodname else ""

    if self._filename:
      filename = os.path.basename(self._filename)
      return "File \"%s\", line %d%s" % (filename,
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
    return text


class ErrorLogBase(object):
  """A stream of errors."""

  def __init__(self):
    self._errors = []
    # An error filter (initially None)
    self._filter = None

  def __len__(self):
    return len(self._errors)

  def __iter__(self):
    return iter(self._errors)

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
      self._errors.append(error)

  def warn(self, opcode, message, *args):
    self._add(Error.at_opcode(opcode, SEVERITY_WARNING, message % args))

  def error(self, opcode, message, details=None):
    self._add(Error.at_opcode(opcode, SEVERITY_ERROR, message, details=details))

  def save(self):
    """Returns a checkpoint that represents the log messages up to now."""
    return CheckPoint(self, len(self._errors))

  def revert_to(self, checkpoint):
    assert checkpoint.log is self
    self._errors = self._errors[:checkpoint.position]

  def print_to_csv_file(self, csv_file):
    for error in self.unique_sorted_errors():
      # pylint: disable=protected-access
      csv_file.writerow(
          [error._filename, error._lineno, error._name, error._message])

  def print_to_file(self, fi):
    for error in self.unique_sorted_errors():
      print >> fi, error

  def unique_sorted_errors(self):
    seen = set()
    for error in self.sorted_errors():
      text = str(error)
      if text not in seen:
        seen.add(text)
        yield error

  def sorted_errors(self):
    # pylint: disable=protected-access
    return sorted(self._errors,
                  key=lambda x: (x._filename, x._lineno))

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)

  def __str__(self):
    io = StringIO.StringIO()
    self.print_to_file(io)
    return io.getvalue()


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  @_error_name("pyi-error")
  def pyi_error(self, opcode, name, error):
    self.error(opcode, "Couldn't import pyi for %r" % name, str(error))

  @_error_name("attribute-error")
  def attribute_error(self, opcode, obj, attr_name):
    on = " on %s" % obj.data[0].name if len(obj.bindings) == 1 else ""
    self.error(opcode, "No attribute %r%s" % (attr_name, on))

  @_error_name("none-attr")
  def none_attr(self, opcode, attr_name):
    self.error(opcode, "Access of attribute %r on NoneType" % (attr_name))

  @_error_name("unbound-type-param")
  def type_param_error(self, opcode, obj, attr_name, type_param_name):
    on = " on %s" % obj.data[0].name if len(obj.bindings) == 1 else ""
    self.error(opcode, "Can't access attribute %r%s" % (attr_name, on),
               "No binding for type parameter %s" % type_param_name)

  @_error_name("name-error")
  def name_error(self, opcode, name):
    self.error(opcode, "Name %r is not defined" % name)

  @_error_name("import-error")
  def import_error(self, opcode, module_name):
    self.error(opcode, "Can't find module %r." % module_name)

  @_error_name("import-error")
  def import_from_error(self, opcode, module, name):
    module_name = module.data[0].name
    self.error(opcode, "Can't find %s.%s" % (module_name, name))

  @_error_name("wrong-arg-count")
  def wrong_arg_count(self, opcode, name, sig, call_arg_count):
    self.error(
        opcode,
        "Function %s was called with %d args instead of expected %d" % (
            name, call_arg_count, sig.mandatory_param_count())
        )

  def _prettyprint_sig(self, sig):
    return re.sub(r"~unknown\d*", "Any", sig)

  def _prettyprint_arg(self, arg):
    if isinstance(arg, abstract.Class):
      return "Type[%s]" % arg.name
    else:
      return arg.name

  @_error_name("wrong-arg-types")
  def wrong_arg_types(self, opcode, name, sig, passed_args):
    """A function was called with the wrong parameter types."""
    message = "Function %s was called with the wrong arguments" % name
    details = "".join([
        "Expected: (", self._prettyprint_sig(str(sig)), ")\n",
        "Actually passed: (", self._prettyprint_sig(
            ", ".join("%s: %s" % (name, self._prettyprint_arg(arg))
                      for name, arg in zip(sig.param_names, passed_args))),
        ")"])
    self.error(opcode, message, details)

  @_error_name("wrong-keyword-args")
  def wrong_keyword_args(self, opcode, name, unused_sig, extra_keywords):
    """A function was called with extra keywords."""
    if len(extra_keywords) == 1:
      message = "Invalid keyword argument %s to function %s" % (
          extra_keywords[0], name)
    else:
      message = "Invalid keyword arguments %s to function %s" % (
          "(" + ", ".join(extra_keywords) + ")", name)
    self.error(opcode, message)

  @_error_name("missing-parameter")
  def missing_parameter(self, opcode, name, unused_sig, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter %r in call to function %s" % (
        missing_parameter, name)
    self.error(opcode, message)

  @_error_name("not-callable")
  def not_callable(self, opcode, function):
    """Calling an object that isn't callable."""
    message = "%r object is not callable" % (function.name)
    self.error(opcode, message)

  @_error_name("duplicate-keyword-argument")
  def duplicate_keyword(self, opcode, name, unused_sig, duplicate):
    self.error(opcode, "function %s got multiple values "
                       "for keyword argument %r" % (name, duplicate))

  def invalid_function_call(self, opcode, error):
    if isinstance(error, abstract.WrongArgCount):
      self.wrong_arg_count(opcode, error.name, error.sig, error.call_arg_count)
    elif isinstance(error, abstract.WrongArgTypes):
      self.wrong_arg_types(opcode, error.name, error.sig, error.passed_args)
    elif isinstance(error, abstract.WrongKeywordArgs):
      self.wrong_keyword_args(
          opcode, error.name, error.sig, error.extra_keywords)
    elif isinstance(error, abstract.MissingParameter):
      self.missing_parameter(
          opcode, error.name, error.sig, error.missing_parameter)
    elif isinstance(error, abstract.NotCallable):
      self.not_callable(opcode, error.obj)
    elif isinstance(error, abstract.DuplicateKeyword):
      self.duplicate_keyword(opcode, error.name, error.sig, error.duplicate)
    else:
      raise AssertionError(error)

  @_error_name("super-error")
  def super_error(self, opcode, arg_count):
    self.error(opcode, "super() takes one or two arguments. %d given." %
               arg_count)

  @_error_name("base-class-error")
  def base_class_error(self, opcode, node, base_var):
    pytd_type = pytd_utils.JoinTypes(t.get_instance_type(node)
                                     for t in base_var.data)
    self.error(opcode, "Invalid base class: %s" % pytd.Print(pytd_type))

  @_error_name("missing-definition")
  def missing_definition(self, item, pytd_filename, py_filename):
    self.error(None, "%s %s declared in pytd %s, but not defined in %s" % (
        type(item).__name__, item.name, pytd_filename, py_filename))

  @_error_name("bad-return-type")
  def bad_return_type(self, opcode, unused_function,
                      actual_pytd, expected_pytd):
    self.error(opcode, "return type is %s, should be %s" % (
        pytd.Print(actual_pytd),
        pytd.Print(expected_pytd)))

  @_error_name("unsupported-operands")
  def unsupported_operands(self, opcode, node, operation, var1, var2):
    left = pytd_utils.JoinTypes(t.to_type(node) for t in var1.data)
    right = pytd_utils.JoinTypes(t.to_type(node) for t in var2.data)
    # TODO(kramm): Display things like '__add__' as '+'
    self.error(opcode, "unsupported operand type(s) for %s: %r and %r" % (
        operation, pytd.Print(left), pytd.Print(right)))

  @_error_name("invalid-annotation")
  def invalid_annotation(self, opcode, name):
    self.error(opcode, "Invalid type annotation for %s. Must be constant" %
               name)

  @_error_name("mro-error")
  def mro_error(self, opcode, name, mro_seqs):
    seqs = []
    for seq in mro_seqs:
      seqs.append("[%s]" % ", ".join(cls.name for cls in seq))
    self.error(opcode, "Class %s has invalid (cyclic?) inheritance: %s." % (
        name, ", ".join(seqs)))

  @_error_name("invalid-directive")
  def invalid_directive(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_WARNING, message, filename=filename, lineno=lineno))

  @_error_name("not-supported-yet")
  def not_supported_yet(self, opcode, feature):
    self.error(opcode, "%s not supported yet" % feature)

  @_error_name("key-error")
  def key_error(self, opcode, key):
    self.error(opcode, "Key %r possibly not in dictionary (yet)" % key)

  @_error_name("python-compiler-error")
  def python_compiler_error(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_ERROR, message, filename=filename, lineno=lineno))
