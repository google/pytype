"""Code and data structures for managing source directives."""

import bisect
import collections
import dataclasses
import logging
import sys
from typing import AbstractSet, Optional

from pytype import blocks
from pytype import config

# directors.parser uses the stdlib ast library, which is much faster than
# libcst, but we rely on ast features that are new in Python 3.9.
# pylint: disable=g-import-not-at-top
if sys.version_info[:2] >= (3, 9):
  from pytype.directors import parser
else:
  from pytype.directors import parser_libcst as parser
# pylint: enable=g-import-not-at-top

log = logging.getLogger(__name__)

SkipFileError = parser.SkipFileError
parse_src = parser.parse_src

_ALL_ERRORS = "*"  # Wildcard for disabling all errors.

_ALLOWED_FEATURES = frozenset(x.flag for x in config.FEATURE_FLAGS)

_FUNCTION_CALL_ERRORS = frozenset((
    # A function call may implicitly access a magic method attribute.
    "attribute-error",
    "duplicate-keyword",
    # Subscripting an annotation is a __getitem__ call.
    "invalid-annotation",
    "missing-parameter",
    "not-instantiable",
    "wrong-arg-count",
    "wrong-arg-types",
    "wrong-keyword-args",
    "unsupported-operands",
))

_ALL_ADJUSTABLE_ERRORS = _FUNCTION_CALL_ERRORS.union((
    "annotation-type-mismatch",
    "bad-return-type",
    "bad-yield-annotation",
    "container-type-mismatch",
    "not-supported-yet",
    "signature-mismatch",
))


class _DirectiveError(Exception):
  pass


class _LineSet:
  """A set of line numbers.

  The data structure is optimized to represent the union of a sparse set
  of integers and ranges of non-negative integers.  This supports the two styles
  of directives: those after a statement apply only to that line and those on
  their own line apply until countered by the opposing directive.
  """

  def __init__(self):
    # Map of line->bool for specific lines, takes precedence over _transitions.
    self._lines = {}
    # A sorted list of the lines at which the range state changes
    # polarity.  It is assumed to initially be false (not in a range).
    # Even positions represent the start of a range, odd positions represent
    # the end of a range.  Thus [2, 5, 10, 12] would include lines 2, 3, 4, 10,
    # and 11.  If the length is odd, then an end of maxint is implied, thus
    # [2, 5, 10] would disable lines 2, 3, 4, 10, 11, 12, ...
    self._transitions = []

  @property
  def lines(self):
    return self._lines

  def set_line(self, line, membership):
    """Set whether a given line is a member of the set."""
    self._lines[line] = membership

  def start_range(self, line, membership):
    """Start a range of lines that are either included/excluded from the set.

    Args:
      line: A line number.
      membership: If True, lines >= line are included in the set (starting
        a range), otherwise they are excluded (ending a range).

    Raises:
      ValueError: if line is less than that of a previous call to start_range().
    """
    last = self._transitions[-1] if self._transitions else -1
    # Assert that lines are monotonically increasing.  This simplifies the
    # logic of adding new lines and ensures that _ranges is sorted.
    if line < last:
      raise ValueError("Line number less than previous start_range() call.")
    # Determine previous membership state (True if the last range has an
    # indefinite end).
    previous = (len(self._transitions) % 2) == 1
    if membership == previous:
      return  # Redundant with previous state, do nothing.
    elif line == last:
      # We have either enable/disable or disable/enable on the same line,
      # cancel them out by popping the previous transition.
      self._transitions.pop()
    else:
      # Normal case - add a transition at this line.
      self._transitions.append(line)

  def __contains__(self, line):
    """Return if a line is a member of the set."""
    # First check for an entry in _lines.
    specific = self._lines.get(line)
    if specific is not None:
      return specific
    # Find the position in _ranges for line.  The polarity of this position
    # determines whether we are inside a range (odd) or outside (even).
    pos = bisect.bisect(self._transitions, line)
    return (pos % 2) == 1

  def get_disable_after(self, line):
    """Get an unclosed disable, if any, that starts after line."""
    if len(self._transitions) % 2 == 1 and self._transitions[-1] >= line:
      return self._transitions[-1]
    return None


class _BlockRanges:
  """A collection of possibly nested start..end ranges from AST nodes."""

  def __init__(self, start_to_end_mapping):
    self._starts = sorted(start_to_end_mapping)
    self._start_to_end = start_to_end_mapping
    self._end_to_start = {v: k for k, v in start_to_end_mapping.items()}

  def has_start(self, line):
    return line in self._start_to_end

  def has_end(self, line):
    return line in self._end_to_start

  def find_outermost(self, line):
    """Find the outermost interval containing line."""
    i = bisect.bisect_left(self._starts, line)
    num_intervals = len(self._starts)
    if i or line == self._starts[0]:
      if i < num_intervals and self._starts[i] == line:
        # line number is start of interval.
        start = self._starts[i]
      else:
        # Skip nested intervals
        while (
            1 < i <= num_intervals and
            self._start_to_end[self._starts[i - 1]] < line):
          i -= 1
        start = self._starts[i - 1]
      end = self._start_to_end[start]
      if line in range(start, end):
        return start, end
    return None, None

  def adjust_end(self, old_end, new_end):
    start = self._end_to_start[old_end]
    self._start_to_end[start] = new_end
    del self._end_to_start[old_end]
    self._end_to_start[new_end] = start


def _collect_bytecode(ordered_code):
  bytecode_blocks = []
  stack = [ordered_code]
  while stack:
    code = stack.pop()
    bytecode_blocks.append(code.original_co_code)
    for const in code.co_consts:
      if isinstance(const, blocks.OrderedCode):
        stack.append(const)
  return bytecode_blocks


def _adjust_line_number(line, allowed_lines, min_line):
  adjusted_line = line
  while adjusted_line not in allowed_lines and adjusted_line >= min_line:
    adjusted_line -= 1
  return adjusted_line if adjusted_line >= min_line else None


def _is_function_call(opcode_name):
  return opcode_name.startswith("CALL_") or opcode_name in {
      "BINARY_SUBSCR",
      "COMPARE_OP",
      "FOR_ITER",
  }


def _is_load_attribute_op(opcode_name):
  """Checks whether the opcode loads an attribute."""
  return (opcode_name.startswith("GET_") or
          opcode_name.startswith("UNPACK_") or
          opcode_name in {
              "LOAD_ATTR",
              "LOAD_METHOD",
              "SETUP_WITH",
          })


def _is_return_op(opcode_name):
  return opcode_name.startswith("YIELD_") or opcode_name == "RETURN_VALUE"


@dataclasses.dataclass
class _OpcodeLines:
  """Stores opcode line numbers for Director.adjust_line_numbers()."""

  store_lines: AbstractSet[int]
  make_function_lines: AbstractSet[int]
  load_attr_lines: AbstractSet[int]
  return_lines: AbstractSet[int]
  call_lines: AbstractSet[int]

  @classmethod
  def from_code(cls, code):
    """Builds an _OpcodeLines from a code object."""
    store_lines = set()
    make_function_lines = set()
    load_attr_lines = set()
    return_lines = set()
    call_lines = set()
    for block in _collect_bytecode(code):
      for opcode in block:
        if opcode.name.startswith("STORE_"):
          store_lines.add(opcode.line)
        elif opcode.name == "MAKE_FUNCTION":
          make_function_lines.add(opcode.line)
        elif _is_load_attribute_op(opcode.name):
          load_attr_lines.add(opcode.line)
        elif _is_return_op(opcode.name):
          return_lines.add(opcode.line)
        elif _is_function_call(opcode.name):
          call_lines.add(opcode.line)
    return cls(store_lines, make_function_lines, load_attr_lines, return_lines,
               call_lines)


class Director:
  """Holds all of the directive information for a source file."""

  def __init__(self, src_tree, errorlog, filename, disable, code):
    """Create a Director for a source file.

    Args:
      src_tree: The source text as an ast.
      errorlog: An ErrorLog object.  Directive errors will be logged to the
        errorlog.
      filename: The name of the source file.
      disable: List of error messages to always ignore.
      code: Optionally, bytecode for adjusting line numbers. If provided,
        directives will be moved to lines at which corresponding opcodes are
        present. Otherwise, directives will be moved to the starting line of
        their containing statement.
    """
    self._filename = filename
    self._errorlog = errorlog
    self._type_comments = {}  # Map from line number to type comment.
    self._variable_annotations = {}  # Map from line number to annotation.
    # Lines that have "type: ignore".  These will disable all errors, and in
    # the future may have other impact (such as not attempting an import).
    self._ignore = _LineSet()
    # Map from error name to lines for which that error is disabled.  Note
    # that _ALL_ERRORS is essentially a wildcard name (it matches all names).
    self._disables = collections.defaultdict(_LineSet)
    # Line numbers of decorators. Since this is used to mark a class or function
    # as decorated, stacked decorators will record the one closest to the
    # definition (i.e. the last one). The python bytecode uses this line number
    # for all the stacked decorator invocations.
    self._decorators = set()
    # Apply global disable, from the command line arguments:
    for error_name in disable:
      self._disables[error_name].start_range(0, True)
    # Store function ranges and return lines to distinguish explicit and
    # implicit returns (the bytecode has a `RETURN None` for implcit returns).
    self.return_lines = set()
    self.block_returns = None
    self._function_ranges = _BlockRanges({})
    # Parse the source code for directives.
    self._parse_src_tree(src_tree, code)

  @property
  def type_comments(self):
    return self._type_comments

  @property
  def annotations(self):
    # It's okay to overwrite type comments with variable annotations here
    # because _FindIgnoredTypeComments in vm.py will flag ignored comments.
    return {**self._type_comments, **self._variable_annotations}

  @property
  def ignore(self):
    return self._ignore

  @property
  def decorators(self):
    return self._decorators

  def _parse_src_tree(self, src_tree, code):
    """Parse a source file, extracting directives from comments."""
    visitor = parser.visit_src_tree(src_tree)
    # TODO(rechen): This check can be removed once parser_libcst is gone.
    if not visitor:
      return
    if code:
      opcode_lines = _OpcodeLines.from_code(code)
    else:
      opcode_lines = None

    self.block_returns = visitor.block_returns
    self.return_lines = visitor.block_returns.all_returns()
    self._function_ranges = _BlockRanges(visitor.function_ranges)
    self.matches = visitor.matches
    self.features = set()

    for line_range, group in visitor.structured_comment_groups.items():
      for comment in group:
        if comment.tool == "type":
          self._process_type(comment.line, comment.data, comment.open_ended,
                             line_range, opcode_lines)
        else:
          assert comment.tool == "pytype"
          try:
            self._process_pytype(comment.line, comment.data, comment.open_ended,
                                 line_range, opcode_lines)
          except _DirectiveError as e:
            self._errorlog.invalid_directive(
                self._filename, comment.line, str(e))
        # Make sure the function range ends at the last "interesting" line.
        if (not isinstance(line_range, parser.Call) and
            self._function_ranges.has_end(line_range.end_line)):
          if opcode_lines:
            end = _adjust_line_number(
                line_range.end_line, opcode_lines.return_lines,
                line_range.start_line)
          else:
            end = line_range.start_line
          self._function_ranges.adjust_end(line_range.end_line, end)

    for annot in visitor.variable_annotations:
      if opcode_lines:
        final_line = _adjust_line_number(
            annot.end_line, opcode_lines.store_lines, annot.start_line)
        if not final_line:
          log.error("No STORE_* opcode found for annotation %r on line %d",
                    annot, annot.end_line)
          continue
      else:
        final_line = annot.start_line
      self._variable_annotations[final_line] = annot.annotation

    for decorator in visitor.decorators:
      # The MAKE_FUNCTION opcode is usually at the 'def' line but pre-3.8 was
      # sometimes somewhere in the last decorator's line range.
      if opcode_lines:
        final_line = _adjust_line_number(
            decorator.end_line, opcode_lines.make_function_lines,
            decorator.start_line)
        if not final_line:
          log.warning("No MAKE_FUNCTION opcode found for decorator on line %d",
                      decorator.end_line)
          continue
      else:
        final_line = decorator.end_line
      self._decorators.add(final_line)

    if visitor.defs_start is not None:
      disables = list(self._disables.items())
      # Add "# type: ignore" to the list of disables that we check.
      disables.append(("Type checking", self._ignore))
      for name, lineset in disables:
        lineno = lineset.get_disable_after(visitor.defs_start)
        if lineno is not None:
          self._errorlog.late_directive(self._filename, lineno, name)

  def _process_type(
      self, line: int, data: str, open_ended: bool,
      line_range: parser.LineRange, opcode_lines: Optional[_OpcodeLines]):
    """Process a type: comment."""
    is_ignore = parser.IGNORE_RE.match(data)
    if not is_ignore and line != line_range.end_line:
      # Warn and discard type comments placed in the middle of expressions.
      self._errorlog.ignored_type_comment(self._filename, line, data)
      return
    if opcode_lines:
      final_line = _adjust_line_number(
          line, opcode_lines.store_lines, line_range.start_line) or line
    else:
      final_line = line_range.start_line
    if is_ignore:
      if open_ended:
        self._ignore.start_range(line, True)
      else:
        self._ignore.set_line(line, True)
        self._ignore.set_line(final_line, True)
    else:
      if final_line in self._type_comments:
        # If we have multiple type comments on the same line, take the last one,
        # but add an error to the log.
        self._errorlog.invalid_directive(
            self._filename, line, "Multiple type comments on the same line.")
      self._type_comments[final_line] = data

  def _process_pytype(
      self, line: int, data: str, open_ended: bool,
      line_range: parser.LineRange, opcode_lines: Optional[_OpcodeLines]):
    """Process a pytype: comment."""
    if not data:
      raise _DirectiveError("Invalid directive syntax.")
    for option in data.split():
      # Parse the command.
      try:
        command, values = option.split("=", 1)
        values = values.split(",")
      except ValueError as e:
        raise _DirectiveError("Invalid directive syntax.") from e
      # Additional commands may be added in the future.  For now, only
      # "disable", "enable", and "features" are supported.
      if command == "disable":
        disable = True
      elif command == "enable":
        disable = False
      elif command == "features":
        features = set(values)
        invalid = features - _ALLOWED_FEATURES
        if invalid:
          raise _DirectiveError(f"Unknown pytype features: {','.join(invalid)}")
        self.features |= features
        continue
      else:
        raise _DirectiveError(f"Unknown pytype directive: '{command}'")
      if not values:
        raise _DirectiveError(
            "Disable/enable must specify one or more error names.")

      def keep(error_name):
        if isinstance(line_range, parser.Call):
          return error_name in _FUNCTION_CALL_ERRORS
        else:
          return True

      for error_name in values:
        if (error_name == _ALL_ERRORS or
            self._errorlog.is_valid_error_name(error_name)):
          if not keep(error_name):
            # Skip the directive if we are in a line range that is irrelevant to
            # it. (Every directive is also recorded in a base LineRange that is
            # never skipped.)
            continue
          lines = self._disables[error_name]
          if open_ended:
            lines.start_range(line, disable)
          else:
            final_line = self._adjust_line_number_for_pytype_directive(
                line, error_name, line_range, opcode_lines)
            if final_line != line:
              # Set the disable on the original line so that, even if we mess up
              # adjusting the line number, silencing an error by adding a
              # disable to the exact line the error is reported on always works.
              lines.set_line(line, disable)
            lines.set_line(final_line, disable)
        else:
          self._errorlog.invalid_directive(
              self._filename, line, f"Invalid error name: '{error_name}'")

  def _adjust_line_number_for_pytype_directive(
      self, line: int, error_class: str, line_range: parser.LineRange,
      opcode_lines: Optional[_OpcodeLines]):
    """Adjusts the line number for a pytype directive."""
    if error_class not in _ALL_ADJUSTABLE_ERRORS:
      return line
    if not opcode_lines:
      return line_range.start_line
    if error_class == "annotation-type-mismatch":
      allowed_lines = (
          opcode_lines.store_lines | opcode_lines.make_function_lines)
    elif error_class == "attribute-error":
      allowed_lines = opcode_lines.load_attr_lines
    elif error_class == "bad-return-type":
      allowed_lines = opcode_lines.return_lines
    elif error_class == "bad-yield-annotation":
      allowed_lines = opcode_lines.make_function_lines
    elif error_class == "invalid-annotation":
      allowed_lines = opcode_lines.make_function_lines
    elif error_class == "not-supported-yet":
      allowed_lines = opcode_lines.store_lines
    elif error_class == "unsupported-operands":
      allowed_lines = opcode_lines.store_lines | opcode_lines.call_lines
    else:
      allowed_lines = opcode_lines.call_lines
    return _adjust_line_number(
        line, allowed_lines, line_range.start_line) or line

  def filter_error(self, error):
    """Return whether the error should be logged.

    This method is suitable for use as an error filter.

    Args:
      error: An error._Error object.

    Returns:
      True iff the error should be included in the log.
    """
    # Always report errors that aren't for this file or do not have a line
    # number.
    if error.filename != self._filename or error.lineno is None:
      return True
    if (error.name == "bad-return-type" and
        error.opcode_name == "RETURN_VALUE" and
        error.lineno not in self.return_lines):
      # We have an implicit "return None". Adjust the line number to the last
      # line of the function.
      _, end = self._function_ranges.find_outermost(error.lineno)
      if end:
        error.set_lineno(end)
    # Treat line=0 as below the file, so we can filter it.
    line = error.lineno or sys.maxsize
    # Report the error if it isn't subject to any ignore or disable.
    return (line not in self._ignore and
            line not in self._disables[_ALL_ERRORS] and
            line not in self._disables[error.name])
