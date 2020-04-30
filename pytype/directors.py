# Lint as: python3
"""Code and data structures for managing source directives."""

import bisect
import collections
import itertools
import keyword
import logging
import re
import sys
import tokenize

from pytype import blocks
from pytype import utils
from six import moves

log = logging.getLogger(__name__)

_DIRECTIVE_RE = re.compile(r"#\s*(pytype|type)\s*:\s?([^#]*)")
_IGNORE_RE = re.compile(r"^ignore(\[.+\])?$")
_CLASS_OR_FUNC_RE = re.compile(r"^(def|class)\s")
_DOCSTRING_RE = re.compile(r"^\s*(\"\"\"|''')")
_DECORATOR_RE = re.compile(r"^\s*@(\w+)([(]|\s*$)")
_ALL_ERRORS = "*"  # Wildcard for disabling all errors.


class _DirectiveError(Exception):
  pass


class SkipFileError(Exception):
  """Exception thrown if we encounter "pytype: skip-file" in the source code."""


class _LineSet(object):
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
      # TODO(dbaum): Consider issuing a warning here.
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

  def get_disable_after(self, lineno):
    """Get an unclosed disable, if any, that starts after lineno."""
    if len(self._transitions) % 2 == 1 and self._transitions[-1] >= lineno:
      return self._transitions[-1]
    return None


class _TypeCommentSet:
  """A set of type comments in a single logical line."""

  @classmethod
  def start(cls, lineno):
    return cls(lineno)

  def __init__(self, start_lineno):
    self.start_line = start_lineno
    self.end_line = None
    self.type_comments = {}


class _FunctionDefinition:
  """Tracks the line numbers of function definitions."""

  @classmethod
  def start(cls, lineno):
    return cls(lineno)

  def __init__(self, start_lineno):
    self._paren_count = 0
    self._start_line = start_lineno
    self._end_line = None

  def add_lpar(self, lineno):
    assert lineno >= self._start_line
    self._paren_count += 1

  def add_rpar(self, lineno):
    if self._end_line is not None:
      return
    self._paren_count -= 1
    if self._paren_count == 0:
      self._end_line = lineno

  def contains(self, lineno):
    if lineno < self._start_line:
      return False
    return self._end_line is None or lineno <= self._end_line


class _VariableAnnotation:
  """Processes a single logical line, looking for a variable annotation."""

  @classmethod
  def start(cls, token):
    self = cls()
    self.add_token(token)
    return self

  def __init__(self):
    self._tokens = []
    self.annotation = ""
    # Set to True when the full annotation has been found, or if we determine
    # that the line does not contain an annotation.
    self.closed = False

  def _accept(self, token):
    if self.closed:
      return False
    # Allow comments and whitespace before the NAME token signifying the start
    # of the annotation.
    return token.exact_type != tokenize.COMMENT and token.string.strip()

  def add_token(self, token):
    """Process a token."""
    if not self._accept(token):
      return
    # Match NAME COLON [annotation] EQUAL. We assume the annotation starts at
    # the beginning of the line, which greatly simplifies matching at the cost
    # of failing to find annotations in lines like `if __random__: v: int = 0`.
    if not self._tokens:
      # Filter out false positives like `else: x = 0`.
      if token.exact_type != tokenize.NAME or keyword.iskeyword(token.string):
        self.closed = True
    elif len(self._tokens) == 1:
      if token.exact_type != tokenize.COLON:
        self.closed = True
    elif token.exact_type == tokenize.EQUAL:
      self.closed = True
    else:
      if self.annotation and self._tokens[-1].end[0] == token.start[0]:
        # Preserve whitespace.
        self.annotation += token.line[self._tokens[-1].end[1]:token.start[1]]
      self.annotation += token.string
    self._tokens.append(token)


def _collect_bytecode(ordered_code):
  bytecode_blocks = []
  stack = [ordered_code]
  while stack:
    code = stack.pop()
    bytecode_blocks.append(code.co_code)
    for const in code.co_consts:
      if isinstance(const, blocks.OrderedCode):
        stack.append(const)
  return bytecode_blocks


class Director(object):
  """Holds all of the directive information for a source file."""

  def __init__(self, src, errorlog, filename, disable):
    """Create a Director for a source file.

    Args:
      src:  The source text as a string.
      errorlog: An ErrorLog object.  Directive errors will be logged to the
          errorlog.
      filename: The name of the source file.
      disable: List of error messages to always ignore.
    """
    self._filename = filename
    self._errorlog = errorlog
    self._type_comments = []  # _TypeCommentSet objects.
    self._variable_annotations = {}  # Map from line number to annotation.
    self._docstrings = set()  # Start lines of docstrings.
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
    # Parse the source code for directives.
    self._parse_source(src)

  @property
  def type_comments(self):
    return collections.ChainMap(*(s.type_comments for s in self._type_comments))

  @property
  def annotations(self):
    # It's okay to overwrite type comments with variable annotations here
    # because _FindIgnoredTypeComments in vm.py will flag ignored comments.
    return {**self.type_comments, **self._variable_annotations}

  @property
  def docstrings(self):
    return sorted(self._docstrings)

  @property
  def ignore(self):
    return self._ignore

  @property
  def decorators(self):
    return self._decorators

  def _parse_source(self, src):
    """Parse a source file, extracting directives from comments."""
    f = moves.StringIO(src)
    defs_start = None
    open_type_comment_set = _TypeCommentSet.start(1)
    open_decorator = False
    last_function_definition = None
    open_variable_annotation = None
    for token in tokenize.generate_tokens(f.readline):
      tok = token.exact_type
      line = token.line
      lineno, col = token.start

      # Check for the first line with a top-level class or function definition.
      if defs_start is None and _CLASS_OR_FUNC_RE.match(line):
        defs_start = lineno

      # Process the token for decorators, function definitions, and comments.
      if tok == tokenize.AT:
        if _DECORATOR_RE.match(line):
          open_decorator = True
      elif tok == tokenize.NAME:
        if open_decorator and token.string in ("class", "def"):
          self.decorators.add(lineno)
          open_decorator = False
        if token.string == "def":
          last_function_definition = _FunctionDefinition.start(lineno)
      elif tok == tokenize.COMMENT:
        self._process_comment(line, lineno, col, open_type_comment_set)
      elif tok == tokenize.LPAR:
        if last_function_definition:
          last_function_definition.add_lpar(lineno)
      elif tok == tokenize.RPAR:
        if last_function_definition:
          last_function_definition.add_rpar(lineno)
      elif tok in (tokenize.NEWLINE, tokenize.ENDMARKER):
        if open_type_comment_set.type_comments:
          open_type_comment_set.end_line = lineno
          self._type_comments.append(open_type_comment_set)
        open_type_comment_set = _TypeCommentSet.start(lineno + 1)

      # Process the token for variable annotations.
      if last_function_definition and last_function_definition.contains(lineno):
        pass  # ignore function annotations
      elif not open_variable_annotation:
        open_variable_annotation = _VariableAnnotation.start(token)
      elif tok in (tokenize.NEWLINE, tokenize.SEMI):
        # NEWLINE indicates the end of a *logical* line of Python code, allowing
        # us to handle annotations split over multiple lines.
        annotation = open_variable_annotation.annotation
        if annotation and open_variable_annotation.closed:
          self._variable_annotations[lineno] = annotation
        open_variable_annotation = None
      else:
        open_variable_annotation.add_token(token)

      # Record docstrings.
      if _DOCSTRING_RE.match(line):
        self._docstrings.add(lineno)

    if defs_start is not None:
      disables = list(self._disables.items())
      # Add "# type: ignore" to the list of disables that we check.
      disables.append(("Type checking", self._ignore))
      for name, lineset in disables:
        lineno = lineset.get_disable_after(defs_start)
        if lineno is not None:
          self._errorlog.late_directive(self._filename, lineno, name)

  def _process_comment(self, line, lineno, col, type_comment_set):
    """Process a single comment."""
    matches = list(_DIRECTIVE_RE.finditer(line[col:]))
    is_nested = bool(matches) and matches[0].start(0) > 0
    for m in matches:
      code = line[:col].strip()
      tool, data = m.groups()
      open_ended = not code
      data = data.strip()
      if tool == "type":
        self._process_type(lineno, code, data, is_nested, type_comment_set)
      elif tool == "pytype":
        try:
          self._process_pytype(lineno, data, open_ended)
        except _DirectiveError as e:
          self._errorlog.invalid_directive(
              self._filename, lineno, utils.message(e))
      else:
        pass  # ignore comments for other tools

  def _process_type(self, lineno, code, data, is_nested, type_comment_set):
    """Process a type: comment."""
    # Discard type comments embedded in larger whole-line comments.
    if not code and is_nested:
      return
    if lineno in type_comment_set.type_comments:
      # If we have multiple type comments on the same line, take the last one,
      # but add an error to the log.
      self._errorlog.invalid_directive(
          self._filename, lineno,
          "Multiple type comments on the same line.")
    # Also supports mypy-style ignore[code, ...] syntax, treated as regular
    # ignores.
    if _IGNORE_RE.match(data):
      if not code:
        self._ignore.start_range(lineno, True)
      else:
        self._ignore.set_line(lineno, True)
    else:
      type_comment_set.type_comments[lineno] = data

  def _process_pytype(self, lineno, data, open_ended):
    """Process a pytype: comment."""
    if not data:
      raise _DirectiveError("Invalid directive syntax.")
    for option in data.split():
      # Parse the command.
      if option == "skip-file":
        raise SkipFileError()
      try:
        command, values = option.split("=", 1)
        values = values.split(",")
      except ValueError:
        raise _DirectiveError("Invalid directive syntax.")
      # Additional commands may be added in the future.  For now, only
      # "disable" and "enable" are supported.
      if command == "disable":
        disable = True
      elif command == "enable":
        disable = False
      else:
        raise _DirectiveError("Unknown pytype directive: '%s'" % command)
      if not values:
        raise _DirectiveError(
            "Disable/enable must specify one or more error names.")
      for error_name in values:
        if (error_name == _ALL_ERRORS or
            self._errorlog.is_valid_error_name(error_name)):
          lines = self._disables[error_name]
          if open_ended:
            lines.start_range(lineno, disable)
          else:
            lines.set_line(lineno, disable)
        else:
          self._errorlog.invalid_directive(
              self._filename, lineno, "Invalid error name: '%s'" % error_name)

  def should_report_error(self, error):
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
    # Treat lineno=0 as below the file, so we can filter it.
    lineno = error.lineno or sys.maxsize
    # Report the error if it isn't subject to any ignore or disable.
    return (lineno not in self._ignore and
            lineno not in self._disables[_ALL_ERRORS] and
            lineno not in self._disables[error.name])

  def adjust_line_numbers(self, code):
    """Uses the bytecode to adjust line numbers."""
    store_lines = set()
    make_function_lines = set()
    for opcode in itertools.chain.from_iterable(_collect_bytecode(code)):
      if opcode.name.startswith("STORE_"):
        store_lines.add(opcode.line)
      elif opcode.name == "MAKE_FUNCTION":
        make_function_lines.add(opcode.line)

    def adjust(line, allowed_lines, min_line=1):
      adjusted_line = line
      while adjusted_line not in allowed_lines and adjusted_line >= min_line:
        adjusted_line -= 1
      return adjusted_line if adjusted_line >= min_line else None

    # Process type comments.
    for type_comment_set in self._type_comments:
      for line, comment in sorted(type_comment_set.type_comments.items()):
        adjusted_line = adjust(line, store_lines, type_comment_set.start_line)
        if not adjusted_line:
          # vm._FindIgnoredTypeComments will take care of error reporting.
          continue
        if line != type_comment_set.end_line:
          self._errorlog.ignored_type_comment(self._filename, line, comment)
          del type_comment_set.type_comments[line]
        elif adjusted_line != line:
          type_comment_set.type_comments[adjusted_line] = comment
          del type_comment_set.type_comments[line]

    # Process decorators.
    for line in sorted(self._decorators):
      adjusted_line = adjust(line, make_function_lines)
      if not adjusted_line:
        log.error(
            "No MAKE_FUNCTION opcode found for decorator on line %d", line)
      elif adjusted_line != line:
        self._decorators.add(adjusted_line)
        self._decorators.remove(line)

    # Process variable annotations.
    for line, annot in sorted(self._variable_annotations.items()):
      adjusted_line = adjust(line, store_lines)
      if not adjusted_line:
        log.error(
            "No STORE_* opcode found for annotation %r on line %d", annot, line)
        del self._variable_annotations[line]
      elif adjusted_line != line:
        self._variable_annotations[adjusted_line] = annot
        del self._variable_annotations[line]
