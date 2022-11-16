"""Code and data structures for storing and displaying errors."""

import collections
import contextlib
import csv
import io
import logging
import re
import sys
import typing
from typing import Callable, IO, Iterable, Optional, Sequence, TypeVar, Union

from pytype import debug
from pytype import matcher
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.overlays import typed_dict as typed_dict_overlay
from pytype.pytd import escape
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import slots
from pytype.pytd import visitors

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

_FuncT = TypeVar("_FuncT", bound=Callable)

_STYLE_BRIGHT = "\x1b[1m"
_STYLE_RESET_ALL = "\x1b[0m"
_FORE_RED = "\x1b[31m"
_FORE_RESET = "\x1b[39m"
_COLOR_ERROR_NAME_TEMPLATE = (_STYLE_BRIGHT + _FORE_RED + "%s" + _FORE_RESET +
                              _STYLE_RESET_ALL)


def _error_name(name) -> Callable[[_FuncT], _FuncT]:
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
  if len(stack) > 1:
    stack = [x for x in stack if not x.skip_in_tracebacks]
  for frame in stack:
    if frame.current_opcode:
      if deduped_stack and (
          frame.current_opcode.line == deduped_stack[-1].current_opcode.line):
        continue
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
  builtin_prefix = "builtins."
  if name.startswith(builtin_prefix):
    ret = f"built-in function {name[len(builtin_prefix):]}"
  else:
    ret = f"function {name}"
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
    opcode_name: Optionally, the name of the opcode that raised the error.
  """

  def __init__(self, severity, message, filename=None, lineno=0,
               methodname=None, details=None, traceback=None, keyword=None,
               keyword_context=None, bad_call=None, opcode_name=None):
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
    self._opcode_name = opcode_name

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
                 opcode_name=opcode.__class__.__name__,
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
  def opcode_name(self):
    return self._opcode_name

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
    method = f", in {self._methodname}" if self._methodname else ""

    if self._filename:
      return "File \"%s\", line %d%s" % (self._filename,
                                         self._lineno,
                                         method)
    elif self._lineno:
      return "Line %d%s" % (self._lineno, method)
    else:
      return ""

  def __str__(self):
    return self.as_string()

  def set_lineno(self, line):
    self._lineno = line

  def as_string(self, *, color=False):
    """Format the error as a friendly string, optionally with shell coloring."""
    pos = self._position()
    if pos:
      pos += ": "
    name = _COLOR_ERROR_NAME_TEMPLATE % (self._name,) if color else self._name
    text = "{}{} [{}]".format(pos, self._message.replace("\n", "\n  "), name)
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
        self.error(stack, e._message, e.details, e.keyword, e.bad_call,  # pylint: disable=protected-access
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

    NOTE: The filter may adjust some properties of the error.
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
            keyword_context=None, lineno=None):
    err = Error.with_stack(stack, SEVERITY_ERROR, message, details=details,
                           keyword=keyword, bad_call=bad_call,
                           keyword_context=keyword_context)
    if lineno:
      err.set_lineno(lineno)
    self._add(err)

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

  def print_to_csv_file(self, fi: IO[str]):
    """Print the errorlog to a csv file."""
    csv_file = csv.writer(fi, delimiter=",", lineterminator="\n")
    for error in self.unique_sorted_errors():
      # pylint: disable=protected-access
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

  def print_to_file(self, fi: IO[str], *, color: bool = False):
    for error in self.unique_sorted_errors():
      print(error.as_string(color=color), file=fi)

  def unique_sorted_errors(self):
    """Gets the unique errors in this log, sorted on filename and lineno."""
    unique_errors = {}
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

  def print_to_stderr(self, *, color=True):
    self.print_to_file(sys.stderr, color=color)

  def __str__(self):
    f = io.StringIO()
    self.print_to_file(f)
    return f.getvalue()


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

  def _print_as_expected_type(self, t: abstract.BaseValue, instance=None):
    """Print abstract value t as a pytd type."""
    if isinstance(t, (abstract.Unknown, abstract.Unsolvable,
                      abstract.Class)) or t.is_late_annotation():
      with t.ctx.pytd_convert.set_output_mode(
          t.ctx.pytd_convert.OutputMode.DETAILED):
        return self._pytd_print(t.get_instance_type(instance=instance))
    elif isinstance(t, abstract.Union):
      return self._join_printed_types(self._print_as_expected_type(o)
                                      for o in t.options)
    elif abstract_utils.is_concrete(t):
      return re.sub(r"(\\n|\s)+", " ",
                    typing.cast(mixin.PythonConstant, t).str_of_constant(
                        self._print_as_expected_type))
    elif (isinstance(t, (abstract.AnnotationClass, abstract.Singleton)) or
          t.cls == t):
      return t.name
    else:
      return f"<instance of {self._print_as_expected_type(t.cls, t)}>"

  def _print_as_actual_type(self, t, literal=False):
    if literal:
      output_mode = t.ctx.pytd_convert.OutputMode.LITERAL
    else:
      output_mode = t.ctx.pytd_convert.OutputMode.DETAILED
    with t.ctx.pytd_convert.set_output_mode(output_mode):
      return self._pytd_print(t.to_type())

  def _print_as_generic_type(self, t):
    generic = pytd_utils.MakeClassOrContainerType(
        t.get_instance_type().base_type,
        t.formal_type_parameters.keys(),
        False)
    with t.ctx.pytd_convert.set_output_mode(
        t.ctx.pytd_convert.OutputMode.DETAILED):
      return self._pytd_print(generic)

  def _print_as_return_types(self, node, bad):
    """Print the actual and expected values for a return type."""
    formal = bad[0].expected.typ
    convert = formal.ctx.pytd_convert
    with convert.set_output_mode(convert.OutputMode.DETAILED):
      expected = self._pytd_print(formal.get_instance_type(node))
      if isinstance(formal, typed_dict_overlay.TypedDictClass):
        expected = expected + "(TypedDict)"
    if "Literal[" in expected:
      output_mode = convert.OutputMode.LITERAL
    else:
      output_mode = convert.OutputMode.DETAILED
    with convert.set_output_mode(output_mode):
      bad_actual = self._pytd_print(pytd_utils.JoinTypes(
          match.actual_binding.data.to_type(node, view=match.view)
          for match in bad))
      actual = bad[0].actual
      if len(actual.bindings) > len(bad):
        full_actual = self._pytd_print(pytd_utils.JoinTypes(
            v.to_type(node) for v in actual.data))
      else:
        full_actual = bad_actual
    # typing.NoReturn is a prettier alias for nothing.
    fmt = lambda ret: "NoReturn" if ret == "nothing" else ret
    error_details = self._prepare_errorlog_details(bad)
    return (fmt(expected), fmt(bad_actual), fmt(full_actual), error_details)

  def _print_as_function_def(self, fn: abstract.Function) -> str:
    convert = fn.ctx.pytd_convert
    name = fn.name.rsplit(".", 1)[-1]  # We want `def bar()` not `def Foo.bar()`
    with convert.set_output_mode(convert.OutputMode.DETAILED):
      pytd_def = convert.value_to_pytd_def(fn.ctx.root_node, fn, name)
    return pytd_utils.Print(pytd_def)

  def _print_protocol_error(self, error: matcher.ProtocolError) -> str:
    """Pretty-print the protocol error."""
    convert = error.left_type.ctx.pytd_convert
    with convert.set_output_mode(convert.OutputMode.DETAILED):
      left = self._pytd_print(error.left_type.get_instance_type())
      protocol = self._pytd_print(error.other_type.get_instance_type())
    if isinstance(error, matcher.ProtocolMissingAttributesError):
      missing = ", ".join(sorted(error.missing))
      return (f"Attributes of protocol {protocol} are not implemented on "
              f"{left}: {missing}")
    else:
      assert isinstance(error, matcher.ProtocolTypeError)
      actual, expected = error.actual_type, error.expected_type
      if (isinstance(actual, abstract.Function) and
          isinstance(expected, abstract.Function)):
        # TODO(b/196434939): When matching a protocol like Sequence[int] the
        # protocol name will be Sequence[int] but the method signatures will be
        # displayed as f(self: Sequence[_T], ...).
        actual = self._print_as_function_def(actual)
        expected = self._print_as_function_def(expected)
        return (f"\nMethod {error.attribute_name} of protocol {protocol} has "
                f"the wrong signature in {left}:\n\n"
                f">> {protocol} expects:\n{expected}\n\n"
                f">> {left} defines:\n{actual}")
      else:
        with convert.set_output_mode(convert.OutputMode.DETAILED):
          actual = self._pytd_print(error.actual_type.to_type())
          expected = self._pytd_print(error.expected_type.to_type())
        return (f"Attribute {error.attribute_name} of protocol {protocol} has "
                f"wrong type in {left}: expected {expected}, got {actual}")

  def _print_noniterable_str_error(self, error):
    """Pretty-print the matcher.NonIterableStrError instance."""
    return (
        f"Note: {error.left_type.name} does not match iterables by default. "
        "Learn more: https://github.com/google/pytype/blob/main/docs/faq.md#why-doesnt-str-match-against-string-iterables")

  def _print_typed_dict_error(self, error):
    """Pretty-print the matcher.TypedDictError instance."""
    ret = ""
    if error.missing:
      ret += "\nTypedDict missing keys: " + ", ".join(error.missing)
    if error.extra:
      ret += "\nTypedDict extra keys: " + ", ".join(error.extra)
    if error.bad:
      ret += "\nTypedDict type errors: "
      for k, bad in error.bad:
        for match in bad:
          actual = self._print_as_actual_type(match.actual_binding.data)
          expected = self._print_as_expected_type(match.expected.typ)
          ret += f"\n  {{'{k}': ...}}: expected {expected}, got {actual}"
    return ret

  def _print_error_details(self, error_details):
    printers = [
        (error_details.protocol, self._print_protocol_error),
        (error_details.noniterable_str, self._print_noniterable_str_error),
        (error_details.typed_dict, self._print_typed_dict_error)
    ]
    return ["\n" + printer(err) if err else "" for err, printer in printers]

  def _prepare_errorlog_details(self, bad):
    """Prepare printable annotation matching errors."""
    details = collections.defaultdict(set)
    for match in bad:
      d = self._print_error_details(match.error_details)
      for i, detail in enumerate(d):
        if detail:
          details[i].add(detail)
    ret = []
    for i in sorted(details.keys()):
      ret.extend(sorted(details[i]))
    return ret

  def _join_printed_types(self, types):
    """Pretty-print the union of the printed types."""
    types = set(types)  # dedup
    if len(types) == 1:
      return next(iter(types))
    elif types:
      literal_contents = set()
      optional = False
      new_types = []
      for t in types:
        if t.startswith("Literal["):
          literal_contents.update(t[len("Literal["):-1].split(", "))
        elif t == "None":
          optional = True
        else:
          new_types.append(t)
      if literal_contents:
        literal = f"Literal[{', '.join(sorted(literal_contents))}]"
        new_types.append(literal)
      if len(new_types) > 1:
        out = f"Union[{', '.join(sorted(new_types))}]"
      else:
        out = new_types[0]
      if optional:
        out = f"Optional[{out}]"
      return out
    else:
      return "nothing"

  def _iter_sig(self, sig):
    """Iterate through a function.Signature object. Focus on a bad parameter."""
    for name in sig.posonly_params:
      yield "", name
    if sig.posonly_params:
      yield ("/", "")
    for name in sig.param_names[sig.posonly_count:]:
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
        type_str = self._print_as_expected_type(bad_param.typ)
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
    self.error(stack, f"Couldn't import pyi for {name!r}", str(error),
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
        stack, f"No attribute {attr_name!r} on {obj_repr}", details=details,
        keyword=attr_name)

  @_error_name("not-writable")
  def not_writable(self, stack, obj, attr_name):
    obj_values = obj.ctx.convert.merge_values([obj])
    obj_repr = self._print_as_actual_type(obj_values)
    self.error(stack, f"Can't assign attribute {attr_name!r} on {obj_repr}",
               keyword=attr_name, keyword_context=obj_repr)

  @_error_name("module-attr")
  def _module_attr(self, stack, binding, attr_name):
    module_name = binding.data.name
    self.error(stack, f"No attribute {attr_name!r} on module {module_name!r}",
               keyword=attr_name, keyword_context=module_name)

  def attribute_error(self, stack, binding, attr_name):
    if attr_name in slots.SYMBOL_MAPPING:
      obj = self._print_as_actual_type(binding.data)
      details = f"No attribute {attr_name!r} on {obj}"
      self._unsupported_operands(stack, attr_name, obj, details=details)
    elif isinstance(binding.data, abstract.Module):
      self._module_attr(stack, binding, attr_name)
    else:
      self._attribute_error(stack, binding, attr_name)

  @_error_name("unbound-type-param")
  def unbound_type_param(self, stack, obj, attr_name, type_param_name):
    self.error(
        stack, f"Can't access attribute {attr_name!r} on {obj.name}",
        f"No binding for type parameter {type_param_name}", keyword=attr_name,
        keyword_context=obj.name)

  @_error_name("name-error")
  def name_error(self, stack, name, details=None):
    self.error(
        stack, f"Name {name!r} is not defined", keyword=name, details=details)

  @_error_name("import-error")
  def import_error(self, stack, module_name):
    self.error(stack, f"Can't find module {module_name!r}.",
               keyword=module_name)

  def _invalid_parameters(self, stack, message, bad_call):
    """Log an invalid parameters error."""
    sig = bad_call.sig
    passed_args = bad_call.passed_args
    bad_param = bad_call.bad_param
    expected = self._print_args(self._iter_expected(sig, bad_param), bad_param)
    literal = "Literal[" in expected
    actual = self._print_args(
        self._iter_actual(sig, passed_args, bad_param, literal), bad_param)
    details = "".join([
        "       Expected: (", expected, ")\n",
        "Actually passed: (", actual,
        ")"])
    if bad_param and bad_param.error_details:
      details += "".join(self._print_error_details(bad_param.error_details))
    self.error(stack, message, details, bad_call=bad_call)

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
          bad_call.bad_param.typ)
      details = (f"{operator_name} on {left_operand} expects "
                 f"{expected_right_operand}")
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
      message = "Invalid keyword argument {} to {}".format(
          extra_keywords[0], _function_name(name))
    else:
      message = "Invalid keyword arguments {} to {}".format(
          "(" + ", ".join(sorted(extra_keywords)) + ")",
          _function_name(name))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("missing-parameter")
  def missing_parameter(self, stack, name, bad_call, missing_parameter):
    """A function call is missing parameters."""
    message = "Missing parameter {!r} in call to {}".format(
        missing_parameter, _function_name(name))
    self._invalid_parameters(stack, message, bad_call)

  @_error_name("not-callable")
  def not_callable(self, stack, func, details=None):
    """Calling an object that isn't callable."""
    if isinstance(func, abstract.InterpreterFunction) and func.is_overload:
      prefix = "@typing.overload-decorated "
    else:
      prefix = ""
    message = f"{prefix}{func.name!r} object is not callable"
    self.error(stack, message, keyword=func.name, details=details)

  @_error_name("not-indexable")
  def not_indexable(self, stack, name, generic_warning=False):
    message = f"class {name} is not indexable"
    if generic_warning:
      self.error(stack, message, f"({name!r} does not subclass Generic)",
                 keyword=name)
    else:
      self.error(stack, message, keyword=name)

  @_error_name("not-instantiable")
  def not_instantiable(self, stack, cls):
    """Instantiating an abstract class."""
    message = "Can't instantiate {} with abstract methods {}".format(
        cls.full_name, ", ".join(sorted(cls.abstract_methods)))
    self.error(stack, message)

  @_error_name("ignored-abstractmethod")
  def ignored_abstractmethod(self, stack, cls_name, method_name):
    message = f"Stray abc.abstractmethod decorator on method {method_name}"
    self.error(stack, message,
               details=f"({cls_name} does not have metaclass abc.ABCMeta)")

  @_error_name("ignored-metaclass")
  def ignored_metaclass(self, stack, cls, metaclass):
    message = f"Metaclass {metaclass} on class {cls} ignored in Python 3"
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
    # Make sure method names are prefixed with the class name.
    if (isinstance(error, function.InvalidParameters) and
        "." not in error.name and error.bad_call.sig.param_names and
        error.bad_call.sig.param_names[0] in ("self", "cls") and
        error.bad_call.passed_args):
      error.name = f"{error.bad_call.passed_args[0][1].full_name}.{error.name}"
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
    elif isinstance(error, typed_dict_overlay.TypedDictKeyMissing):
      self.typed_dict_error(stack, error.typed_dict, error.name)
    elif isinstance(error, function.DictKeyMissing):
      # We don't report DictKeyMissing because the false positive rate is high.
      pass
    else:
      raise AssertionError(error)

  @_error_name("base-class-error")
  def base_class_error(self, stack, base_var, details=None):
    base_cls = self._join_printed_types(
        self._print_as_expected_type(t) for t in base_var.data)
    self.error(stack, f"Invalid base class: {base_cls}",
               details=details, keyword=base_cls)

  @_error_name("bad-return-type")
  def bad_return_type(self, stack, node, bad):
    """Logs a [bad-return-type] error."""
    expected, bad_actual, full_actual, error_details = (
        self._print_as_return_types(node, bad))
    if full_actual == bad_actual:
      message = "bad return type"
    else:
      message = f"bad option {bad_actual!r} in return type"
    details = ["         Expected: ", expected, "\n",
               "Actually returned: ", full_actual]
    details.extend(error_details)
    self.error(stack, message, "".join(details))

  @_error_name("bad-return-type")
  def any_return_type(self, stack):
    """Logs a [bad-return-type] error."""
    message = "Return type may not be Any"
    details = ["Pytype is running with features=no-return-any, which does " +
               "not allow Any as a return type."]
    self.error(stack, message, "".join(details))

  @_error_name("bad-yield-annotation")
  def bad_yield_annotation(self, stack, name, annot, is_async):
    func = ("async " if is_async else "") + f"generator function {name}"
    actual = self._print_as_expected_type(annot)
    message = f"Bad return type {actual!r} for {func}"
    if is_async:
      details = "Expected AsyncGenerator, AsyncIterable or AsyncIterator"
    else:
      details = "Expected Generator, Iterable or Iterator"
    self.error(stack, message, details)

  @_error_name("bad-concrete-type")
  def bad_concrete_type(self, stack, node, bad, details=None):
    expected, actual, _, error_details = self._print_as_return_types(node, bad)
    full_details = ["       Expected: ", expected, "\n",
                    "Actually passed: ", actual]
    if details:
      full_details.append("\n" + details)
    full_details.extend(error_details)
    self.error(
        stack, "Invalid instantiation of generic class", "".join(full_details))

  def _show_variable(self, var):
    """Show variable as 'name: typ' or 'pyval: typ' if available."""
    if not var.data:
      return self._pytd_print(pytd.NothingType())
    val = var.data[0]
    name = val.ctx.vm.get_var_name(var)
    typ = self._join_printed_types(
        self._print_as_actual_type(t) for t in var.data)
    if name:
      return f"'{name}: {typ}'"
    elif len(var.data) == 1 and hasattr(val, "pyval"):
      name = abstract_utils.show_constant(val)
      return f"'{name}: {typ}'"
    else:
      return f"'{typ}'"

  def unsupported_operands(self, stack, operator, var1, var2):
    left = self._show_variable(var1)
    right = self._show_variable(var2)
    details = f"No attribute {operator!r} on {left}"
    if operator in slots.REVERSE_NAME_MAPPING:
      details += f" or {slots.REVERSE_NAME_MAPPING[operator]!r} on {right}"
    self._unsupported_operands(stack, operator, left, right, details=details)

  @_error_name("unsupported-operands")
  def _unsupported_operands(self, stack, operator, *operands, details=None):
    """Unsupported operands."""
    # `operator` is sometimes the symbol and sometimes the method name, so we
    # need to check for both here.
    # TODO(mdemello): This is a mess, we should fix the call sites.
    if operator in slots.SYMBOL_MAPPING:
      symbol = slots.SYMBOL_MAPPING[operator]
    else:
      symbol = operator
    cmp = operator in slots.COMPARES or symbol in slots.COMPARES
    args = " and ".join(str(operand) for operand in operands)
    if cmp:
      details = f"Types {args} are not comparable."
      self.error(stack, f"unsupported operand types for {symbol}",
                 details=details)
    else:
      self.error(stack, f"unsupported operand type(s) for {symbol}: {args}",
                 details=details)

  def invalid_annotation(self,
                         stack,
                         annot: Optional[Union[str, abstract.BaseValue]],
                         details=None,
                         name=None):
    if isinstance(annot, abstract.BaseValue):
      annot = self._print_as_expected_type(annot)
    self._invalid_annotation(stack, annot, details, name)

  def _print_params_helper(self, param_or_params):
    if isinstance(param_or_params, abstract.BaseValue):
      return self._print_as_expected_type(param_or_params)
    else:
      return "[{}]".format(
          ", ".join(self._print_params_helper(p) for p in param_or_params))

  def wrong_annotation_parameter_count(
      self, stack, annot: abstract.BaseValue,
      params: Sequence[abstract.BaseValue], expected_count: int,
      template: Optional[Iterable[str]] = None):
    """Log an error for an annotation with the wrong number of parameters."""
    base_type = self._print_as_expected_type(annot)
    full_type = base_type + self._print_params_helper(params)
    if template:
      templated_type = f"{base_type}[{', '.join(template)}]"
    else:
      templated_type = base_type
    details = "%s expected %d parameter%s, got %d" % (
        templated_type, expected_count, "" if expected_count == 1 else "s",
        len(params))
    self._invalid_annotation(stack, full_type, details, name=None)

  def invalid_ellipses(self, stack, indices, container_name):
    if indices:
      details = "Not allowed at {} {} in {}".format(
          "index" if len(indices) == 1 else "indices",
          ", ".join(str(i) for i in sorted(indices)),
          container_name)
      self._invalid_annotation(stack, "Ellipsis", details, None)

  def ambiguous_annotation(
      self,
      stack,
      options: Optional[Union[str, Iterable[abstract.BaseValue]]],
      name=None):
    """Log an ambiguous annotation."""
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
    annot_string = f"{annot_string!r} " if annot_string else ""
    self.error(stack, f"Invalid type annotation {annot_string}{suffix}",
               details=details)

  @_error_name("mro-error")
  def mro_error(self, stack, name, mro_seqs, details=None):
    seqs = []
    for seq in mro_seqs:
      seqs.append(f"[{', '.join(cls.name for cls in seq)}]")
    suffix = f": {', '.join(seqs)}" if seqs else ""
    msg = f"{name} has invalid inheritance{suffix}."
    self.error(stack, msg, keyword=name, details=details)

  @_error_name("invalid-directive")
  def invalid_directive(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_WARNING, message, filename=filename, lineno=lineno))

  @_error_name("late-directive")
  def late_directive(self, filename, lineno, name):
    message = f"{name} disabled from here to the end of the file"
    details = ("Consider limiting this directive's scope or moving it to the "
               "top of the file.")
    self._add(Error(SEVERITY_WARNING, message, details=details,
                    filename=filename, lineno=lineno))

  @_error_name("not-supported-yet")
  def not_supported_yet(self, stack, feature, details=None):
    self.error(stack, f"{feature} not supported yet", details=details)

  @_error_name("python-compiler-error")
  def python_compiler_error(self, filename, lineno, message):
    self._add(Error(
        SEVERITY_ERROR, message, filename=filename, lineno=lineno))

  @_error_name("recursion-error")
  def recursion_error(self, stack, name):
    self.error(stack, f"Detected recursion in {name}", keyword=name)

  @_error_name("redundant-function-type-comment")
  def redundant_function_type_comment(self, filename, lineno):
    self._add(Error(
        SEVERITY_ERROR,
        "Function type comments cannot be used with annotations",
        filename=filename, lineno=lineno))

  @_error_name("invalid-function-type-comment")
  def invalid_function_type_comment(self, stack, comment, details=None):
    self.error(stack, f"Invalid function type comment: {comment}",
               details=details)

  @_error_name("ignored-type-comment")
  def ignored_type_comment(self, filename, lineno, comment):
    self._add(Error(
        SEVERITY_WARNING, f"Stray type comment: {comment}",
        filename=filename, lineno=lineno))

  @_error_name("invalid-typevar")
  def invalid_typevar(self, stack, comment, bad_call=None):
    if bad_call:
      self._invalid_parameters(stack, comment, bad_call)
    else:
      self.error(stack, f"Invalid TypeVar: {comment}")

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
    msg = f"Cannot unpack {vals_str} into {vars_str}"
    self.error(stack, msg, keyword=vals_str)

  @_error_name("reveal-type")
  def reveal_type(self, stack, node, var):
    types = [
        self._print_as_actual_type(b.data)
        for b in abstract_utils.expand_type_parameter_instances(var.bindings)
        if node.HasCombination([b])]
    self.error(stack, self._join_printed_types(types))

  @_error_name("assert-type")
  def assert_type(self, stack, node, var, typ=None):
    """Check that a variable type matches its expected value."""

    types = [
        self._print_as_actual_type(b.data)
        for b in abstract_utils.expand_type_parameter_instances(var.bindings)
        if node.HasCombination([b])]
    actual = self._join_printed_types(types)

    # assert_type(x) checks that x is not Any
    if typ is None:
      if types == ["Any"] or types == ["typing.Any"]:
        self.error(stack, f"Asserted type was {actual}")
      return

    try:
      expected = abstract_utils.get_atomic_python_constant(typ, str)
    except abstract_utils.ConversionError:
      # NOTE: Converting types to strings is provided as a fallback, but is not
      # really supported, since there are issues around name resolution.
      ctx = typ.data[0].ctx
      typ = ctx.annotation_utils.extract_annotation(node, typ, "assert_type",
                                                    ctx.vm.simple_stack())
      node, typ = ctx.vm.init_class(node, typ)
      wanted = [
          self._print_as_actual_type(b.data)
          for b in abstract_utils.expand_type_parameter_instances(typ.bindings)
          if node.HasCombination([b])]
      expected = self._join_printed_types(wanted)
    if actual != expected:
      details = f"Expected: {expected}\n  Actual: {actual}"
      self.error(stack, actual, details=details)

  @_error_name("annotation-type-mismatch")
  def annotation_type_mismatch(
      self, stack, annot, binding, name, error_details, details=None, *,
      typed_dict=None):
    """Invalid combination of annotation and assignment."""
    if annot is None:
      return
    annot_string = self._print_as_expected_type(annot)
    if isinstance(annot, typed_dict_overlay.TypedDictClass):
      annot_string = annot_string + "(TypedDict)"
    literal = "Literal[" in annot_string
    actual_string = self._print_as_actual_type(binding.data, literal=literal)
    if actual_string == "None":
      annot_string += f" (Did you mean 'typing.Optional[{annot_string}]'?)"
    additional_details = f"\n\n{details}" if details else ""
    additional_details += "".join(self._print_error_details(error_details))
    details = (f"Annotation: {annot_string}\n" +
               f"Assignment: {actual_string}" +
               additional_details)
    if len(binding.variable.bindings) > 1:
      # Joining the printed types rather than merging them before printing
      # ensures that we print all of the options when 'Any' is among them.
      # We don't need to print this if there is only 1 unique type.
      print_types = {self._print_as_actual_type(v, literal=literal)
                     for v in binding.variable.data}
      if len(print_types) > 1:
        details += ("\nIn assignment of type: "
                    f"{self._join_printed_types(print_types)}")
    if typed_dict is not None:
      suffix = f" for key {name} in TypedDict {typed_dict.class_name}"
    elif name is not None:
      suffix = " for " + name
    else:
      suffix = ""
    err_msg = f"Type annotation{suffix} does not match type of assignment"
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
    for base in obj.cls.mro:
      if isinstance(base, abstract.ParameterizedClass):
        cls = base
        break
    else:
      assert False, f"{obj.cls.full_name} is not a container"
    details = f"Container: {self._print_as_generic_type(cls)}\n"
    allowed_contained = ""
    new_contained = ""
    for formal in cls.formal_type_parameters.keys():
      if formal in mutations:
        params, values, _ = mutations[formal]
        allowed_content = self._print_as_expected_type(
            cls.get_formal_type_parameter(formal))
        new_content = self._join_printed_types(
            sorted(self._print_as_actual_type(v)
                   for v in set(values.data) - set(params.data)))
        allowed_contained += f"  {formal}: {allowed_content}\n"
        new_contained += f"  {formal}: {new_content}\n"
    annotation = self._print_as_expected_type(cls)
    details += ("Allowed contained types (from annotation %s):\n%s"
                "New contained types:\n%s") % (
                    annotation, allowed_contained, new_contained)
    suffix = "" if name is None else " for " + name
    err_msg = f"New container type{suffix} does not match type annotation"
    self.error(stack, err_msg, details=details)

  @_error_name("invalid-function-definition")
  def invalid_function_definition(self, stack, msg):
    self.error(stack, msg)

  @_error_name("typed-dict-error")
  def typed_dict_error(self, stack, obj, name):
    """Accessing a nonexistent key in a typed dict.

    Args:
      stack: the frame stack
      obj: the typed dict instance
      name: the key name
    """
    if name:
      err_msg = f"TypedDict {obj.class_name} does not contain key {name}"
    else:
      err_msg = (f"TypedDict {obj.class_name} requires all keys to be constant "
                 "strings")
    self.error(stack, err_msg)

  @_error_name("final-error")
  def _overriding_final(self, stack, cls, base, name, *, is_method, details):
    desc = "method" if is_method else "class attribute"
    msg = (f"Class {cls.name} overrides final {desc} {name}, "
           f"defined in base class {base.name}")
    self.error(stack, msg, details=details)

  def overriding_final_method(self, stack, cls, base, name, details=None):
    self._overriding_final(stack, cls, base, name, details=details,
                           is_method=True)

  def overriding_final_attribute(self, stack, cls, base, name, details=None):
    self._overriding_final(stack, cls, base, name, details=details,
                           is_method=False)

  def _normalize_signature(self, signature):
    """If applicable, converts from `f(self: A, ...)` to `A.f(self, ...)`."""
    self_name = signature.param_names[0]
    if "." not in signature.name and self_name in signature.annotations:
      annotations = dict(signature.annotations)
      self_annot = annotations.pop(self_name)
      signature = signature._replace(
          name=f"{self_annot.full_name}.{signature.name}",
          annotations=annotations)
    return signature

  @_error_name("signature-mismatch")
  def overriding_signature_mismatch(self, stack, base_signature,
                                    class_signature, details=None):
    """Signature mismatch between overridden and overriding class methods."""
    base_signature = self._normalize_signature(base_signature)
    class_signature = self._normalize_signature(class_signature)
    signatures = (f"Base signature: '{base_signature}'.\n"
                  f"Subclass signature: '{class_signature}'.")
    if details:
      details = signatures + "\n" + details
    else:
      details = signatures
    self.error(stack, "Overriding method signature mismatch", details=details)

  @_error_name("final-error")
  def assigning_to_final(self, stack, name, local):
    """Attempting to reassign a variable annotated with Final."""
    obj = "variable" if local else "attribute"
    err_msg = f"Assigning to {obj} {name}, which was annotated with Final"
    self.error(stack, err_msg)

  @_error_name("final-error")
  def subclassing_final_class(self, stack, base_var, details=None):
    base_cls = self._join_printed_types(
        self._print_as_expected_type(t) for t in base_var.data)
    self.error(stack, f"Cannot subclass final class: {base_cls}",
               details=details, keyword=base_cls)

  @_error_name("final-error")
  def bad_final_decorator(self, stack, obj, details=None):
    name = getattr(obj, "name", None)
    if not name:
      typ = self._print_as_expected_type(obj)
      name = f"object of type {typ}"
    msg = f"Cannot apply @final decorator to {name}"
    details = "@final can only be applied to classes and methods."
    self.error(stack, msg, details=details)

  @_error_name("final-error")
  def invalid_final_type(self, stack, details=None):
    msg = "Invalid use of typing.Final"
    details = ("Final may only be used as the outermost type in assignments "
               "or variable annotations.")
    self.error(stack, msg, details=details)

  @_error_name("match-error")
  def match_posargs_count(self, stack, cls, posargs, match_args, details=None):
    msg = (f"{cls.name}() accepts {match_args} positional sub-patterns"
           f" ({posargs} given)")
    self.error(stack, msg, details=details)

  @_error_name("incomplete-match")
  def incomplete_match(self, stack, line, cases, details=None):
    cases = ", ".join(cases)
    msg = f"The enum match is missing the following cases: {cases}"
    self.error(stack, msg, details=details, lineno=line)

  @_error_name("redundant-match")
  def redundant_match(self, stack, case, details=None):
    msg = f"This enum case has already been covered: {case}."
    self.error(stack, msg, details=details)


def get_error_names_set():
  return _ERROR_NAMES
