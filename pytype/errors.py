"""Code and data structures for storing and displaying errors."""

import os
import StringIO
import sys


from pytype import abstract
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


# "Error level" enum for distinguishing between warnings and errors:
SEVERITY_WARNING = 1
SEVERITY_ERROR = 2


class CheckPoint(object):
  """Represents a position in an error log."""

  def __init__(self, log, position):
    self.log = log
    self.position = position


class Error(object):
  """Representation of an error in the error log."""

  def __init__(self, severity, filename, lineno, column,
               methodname, linetext, message):
    self.severity = severity
    self.filename = filename
    self.lineno = lineno
    self.column = column
    self.methodname = methodname
    self.linetext = linetext
    self.message = message

  def position(self):
    """Return human-readable filename + line number."""
    method = ", in %s" % self.methodname if self.methodname else ""

    if self.filename:
      filename = os.path.basename(self.filename)
      return "File \"%s\", line %d%s" % (filename,
                                         self.lineno,
                                         method)
    elif self.lineno:
      return "Line %d%s" % (self.lineno, method)
    else:
      return ""

  def __str__(self):
    pos = self.position()
    return (pos + ": " if pos else "") + self.message.replace("\n", "\n  ")


class ErrorLogBase(object):
  """A stream of errors."""

  def __init__(self):
    self.errors = []

  def __len__(self):
    return len(self.errors)

  def __nonzero__(self):
    return bool(len(self))

  def __iter__(self):
    return iter(self.errors)

  def _add(self, severity, opcode, message, args):
    self.errors.append(Error(
        severity=severity,
        filename=opcode.code.co_filename if opcode else None,
        lineno=opcode.line if opcode else None,
        column=None,
        methodname=opcode.code.co_name if opcode else None,
        linetext=None,
        message=message % args))

  def warn(self, opcode, message, *args):
    self._add(SEVERITY_WARNING, opcode, message, args)

  def error(self, opcode, message, *args):
    self._add(SEVERITY_ERROR, opcode, message, args)

  def save(self):
    """Returns a checkpoint that represents the log messages up to now."""
    return CheckPoint(self, len(self.errors))

  def revert_to(self, checkpoint):
    assert checkpoint.log is self
    self.errors = self.errors[:checkpoint.position]

  def print_to_file(self, fi):
    seen = set()
    for error in sorted(self.errors,
                        key=lambda x: utils.numeric_sort_key(x.position())):
      text = str(error)
      if text not in seen:
        print >>fi, error
        seen.add(text)

  def print_to_stderr(self):
    self.print_to_file(sys.stderr)

  def __str__(self):
    io = StringIO.StringIO()
    self.print_to_file(io)
    return io.getvalue()


class ErrorLog(ErrorLogBase):
  """ErrorLog with convenience functions."""

  def pyi_error(self, e):
    self.errors.append(Error(
        severity=SEVERITY_ERROR,
        filename=e.filename,
        lineno=e.lineno,
        column=e.column,
        methodname=None,
        linetext=e.line,
        message=e.msg))

  def attribute_error(self, opcode, obj, attr_name):
    on = " on %s" % obj.data[0].name if obj.values else ""
    self.error(opcode, "No attribute %r%s" % (attr_name, on))

  def name_error(self, opcode, name):
    self.error(opcode, "Name %r is not defined" % name)

  def import_error(self, opcode, module_name):
    self.error(opcode, "Can't find module %r" % module_name)

  def wrong_arg_count(self, opcode, sig, call_arg_count):
    self.error(
        opcode,
        "Function %s was called with %d args instead of expected %d" % (
            sig.name, call_arg_count, sig.mandatory_param_count())
        )

  def wrong_arg_types(self, opcode, sig, passed_args):
    """A function was called with the wrong parameter types."""
    message = "".join([
        "Function %s was called with the wrong arguments\n" % sig.name,
        "Expected: (", str(sig), ")\n",
        "Actually passed: (",
        ", ".join("%s: %s" % (name, arg.name)
                  for name, arg in zip(sig.param_names, passed_args)),
        ")"])
    self.error(opcode, message)

  def invalid_function_call(self, opcode, error):
    if isinstance(error, abstract.WrongArgCount):
      self.wrong_arg_count(opcode, error.sig, error.call_arg_count)
    elif isinstance(error, abstract.WrongArgTypes):
      self.wrong_arg_types(opcode, error.sig, error.passed_args)
    else:
      raise AssertionError(error)

  def index_error(self, opcode, container, unused_index):
    if container.data:
      out_of = " out of %s" % container.data[0].name
    else:
      out_of = ""
    self.error(opcode, "Can't retrieve item%s. Empty?",
               out_of)

  def super_error(self, opcode, arg_count):
    self.error(opcode, "super() takes one or two arguments. %d given.",
               arg_count)

  def base_class_error(self, opcode, base_var):
    pytd_type = pytd_utils.JoinTypes(t.get_instance_type()
                                     for t in base_var.data)
    self.error(opcode, "Invalid base class: %s", pytd.Print(pytd_type))

  def missing_definition(self, item, pytd_filename, py_filename):
    self.error(None, "%s %s declared in pytd %s, but not defined in %s",
               type(item).__name__, item.name, pytd_filename, py_filename)

  def bad_return_type(self, opcode, unused_function, actual, expected):
    self.error(opcode, "return type is %s, should be %s",
               pytd.Print(actual.to_type()),
               pytd.Print(expected))

  def unsupported_operands(self, opcode, operation, var1, var2):
    left = pytd_utils.JoinTypes(t.to_type() for t in var1.data)
    right = pytd_utils.JoinTypes(t.to_type() for t in var2.data)
    # TODO(kramm): Display things like '__add__' as '+'
    self.error(opcode, "unsupported operand type(s) for %s: %r and %r" % (
        operation, pytd.Print(left), pytd.Print(right)))

  def invalid_annotation(self, opcode, name):
    self.error(opcode, "Invalid type annotation for %s. Must be constant" %
               name)
