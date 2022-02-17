"""Code and data structures for managing source directives."""

import bisect
import collections
import dataclasses
import logging
import re
import sys
from typing import AbstractSet, Optional

import libcst

from pytype import blocks
from pytype import utils

log = logging.getLogger(__name__)

_DIRECTIVE_RE = re.compile(r"#\s*(pytype|type)\s*:\s?([^#]*)")
# Also supports mypy-style ignore[code, ...] syntax, treated as regular ignores.
_IGNORE_RE = re.compile(r"^ignore(\[.+\])?$")
_ALL_ERRORS = "*"  # Wildcard for disabling all errors.

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
))


class _DirectiveError(Exception):
  pass


class SkipFileError(Exception):
  """Exception thrown if we encounter "pytype: skip-file" in the source code."""


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


@dataclasses.dataclass(frozen=True)
class _LineRange:
  start_line: int
  end_line: int


@dataclasses.dataclass(frozen=True)
class _StructuredComment:
  """A structured comment.

  Attributes:
    line: The line number.
    tool: The tool label, e.g., "type" for "# type: int".
    data: The data, e.g., "int" for "# type: int".
    open_ended: True if the comment appears on a line by itself (i.e., it is
     open-ended rather than attached to a line of code).
  """
  line: int
  tool: str
  data: str
  open_ended: bool


@dataclasses.dataclass(frozen=True)
class _Attribute(_LineRange):
  """Tag to identify attribute accesses."""


@dataclasses.dataclass(frozen=True)
class _Call(_LineRange):
  """Tag to identify function calls."""


@dataclasses.dataclass(frozen=True)
class _VariableAnnotation(_LineRange):
  annotation: str


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


class _ParseVisitor(libcst.CSTVisitor):
  """Visitor for parsing a source tree.

  Attributes:
    structured_comment_groups: Ordered map from a line range to the "type:" and
      "pytype:" comments within the range. Line ranges come in several flavors:
      * Instances of the base _LineRange class represent single logical
        statements. These ranges are ascending and non-overlapping and record
        all structured comments found.
      * Instances of the _Attribute and _Call subclasses represent attribute
        accesses and function calls, respectively. These ranges are ascending by
        start_line but may overlap and only record "pytype:" comments.
    variable_annotations: Sequence of PEP 526-style variable annotations with
      line numbers.
    decorators: Sequence of lines at which decorated functions are defined.
    defs_start: The line number at which the first class or function definition
      appears, if any.
  """

  METADATA_DEPENDENCIES = (libcst.metadata.PositionProvider,
                           libcst.metadata.ParentNodeProvider,)

  def __init__(self):
    self.structured_comment_groups = collections.OrderedDict()
    self.variable_annotations = []
    self.decorators = []
    self.defs_start = None

  def _get_containing_groups(self, start_line, end_line=None):
    """Get _StructuredComment groups that fully contain the given line range."""
    end_line = end_line or start_line
    # Since the visitor processes the source file roughly from top to bottom,
    # the given line range should be within a recently added comment group. We
    # also keep the groups ordered. So we do a reverse search and stop as soon
    # as we hit a statement that does not overlap with our given range.
    for line_range, group in reversed(self.structured_comment_groups.items()):
      if (line_range.start_line <= start_line and
          end_line <= line_range.end_line):
        yield (line_range, group)
      elif (not isinstance(line_range, (_Attribute, _Call)) and
            line_range.end_line < start_line):
        return

  def _has_containing_group(self, start_line, end_line=None):
    for line_range, _ in self._get_containing_groups(start_line, end_line):
      if not isinstance(line_range, (_Attribute, _Call)):
        return True
    return False

  def _add_structured_comment_group(self, start_line, end_line, cls=_LineRange):
    """Adds an empty _StructuredComment group with the given line range."""
    if cls is _LineRange and self._has_containing_group(start_line, end_line):
      return
    # We keep structured_comment_groups ordered by inserting the new line range
    # at the end, then absorbing line ranges that the new range contains and
    # calling move_to_end() on ones that should come after it. We encounter line
    # ranges in roughly ascending order, so this reordering is not expensive.
    keys_to_absorb = []
    keys_to_move = []
    for line_range in reversed(self.structured_comment_groups):
      if (cls is _LineRange and
          start_line <= line_range.start_line and
          line_range.end_line <= end_line):
        if type(line_range) is _LineRange:  # pylint: disable=unidiomatic-typecheck
          keys_to_absorb.append(line_range)
        else:
          keys_to_move.append(line_range)
      elif line_range.start_line > start_line:
        keys_to_move.append(line_range)
      else:
        break
    self.structured_comment_groups[cls(start_line, end_line)] = new_group = []
    for k in reversed(keys_to_absorb):
      new_group.extend(self.structured_comment_groups[k])
      del self.structured_comment_groups[k]
    for k in reversed(keys_to_move):
      self.structured_comment_groups.move_to_end(k)

  def _process_comment(self, line, comment, open_ended):
    """Process a single comment."""
    matches = list(_DIRECTIVE_RE.finditer(comment))
    if not matches:
      return
    is_nested = matches[0].start(0) > 0
    for m in matches:
      tool, data = m.groups()
      assert data is not None
      data = data.strip()
      if tool == "pytype" and data == "skip-file":
        # Abort immediately to avoid unnecessary processing.
        raise SkipFileError()
      if tool == "type" and open_ended and is_nested:
        # Discard type comments embedded in larger whole-line comments.
        continue
      structured_comment = _StructuredComment(line, tool, data, open_ended)
      for line_range, group in self._get_containing_groups(line):
        if not isinstance(line_range, (_Attribute, _Call)):
          # A structured comment belongs to exactly one logical statement.
          group.append(structured_comment)
          break
        elif not open_ended and (
            tool == "pytype" or (tool == "type" and _IGNORE_RE.match(data))):
          # A "type: ignore" or "pytype:" comment can additionally belong to any
          # number of overlapping attribute accesses and function calls.
          group.append(structured_comment)
      else:
        raise AssertionError("Could not find a line range for comment "
                             f"{structured_comment} on line {line}")

  def _get_position(self, node):
    return self.get_metadata(libcst.metadata.PositionProvider, node)

  # Comments are found inside TrailingWhitespace and EmptyLine nodes. We visit
  # all the nodes that can contain a TrailingWhitespace node and add a comment
  # group for each of them, then populate the groups with TrailingWhitespace
  # comments. EmptyLine comments form their own single-line groups. Note that
  # comment.start should be used to get the line at which a comment is located;
  # comment.end is at column 0 of the following line.

  def _visit_comment_owner(self, node, cls=_LineRange):
    pos = self._get_position(node)
    self._add_structured_comment_group(pos.start.line, pos.end.line, cls)

  def visit_Decorator(self, node):
    self._visit_comment_owner(node)

  def visit_SimpleStatementLine(self, node):
    self._visit_comment_owner(node)

  def visit_SimpleStatementSuite(self, node):
    self._visit_comment_owner(node)

  def visit_IndentedBlock(self, node):
    # An indented block has a "header" child that holds any trailing comment
    # from the block's header, e.g.:
    #   if __random__:  # header comment
    #     indented_block
    # The comment's line range goes from the first line of the header to the
    # comment line.
    parent = self.get_metadata(libcst.metadata.ParentNodeProvider, node)
    # visit_FunctionDef takes care of adding line ranges for FunctionDef.
    if not isinstance(parent, libcst.FunctionDef):
      start = self._get_position(parent).start
      end = self._get_position(node.header).start
      self._add_structured_comment_group(start.line, end.line)

  def visit_ParenthesizedWhitespace(self, node):
    self._visit_comment_owner(node)

  def visit_Attribute(self, node):
    self._visit_comment_owner(node, cls=_Attribute)

  def visit_Call(self, node):
    self._visit_comment_owner(node, cls=_Call)

  def visit_Comparison(self, node):
    self._visit_comment_owner(node, cls=_Call)

  def visit_Subscript(self, node):
    self._visit_comment_owner(node, cls=_Call)

  def visit_TrailingWhitespace(self, node):
    if node.comment:
      line = self._get_position(node).start.line
      self._process_comment(line, node.comment.value, open_ended=False)

  def visit_EmptyLine(self, node):
    if node.comment:
      line = self._get_position(node).start.line
      self._add_structured_comment_group(line, line)
      self._process_comment(line, node.comment.value, open_ended=True)

  def visit_AnnAssign(self, node):
    if not node.value:
      # TODO(b/167613685): Stop discarding annotations without values.
      return
    pos = self._get_position(node)
    # Gets a string representation of the annotation.
    annotation = re.sub(
        r"\s*(#.*)?\n\s*", "",
        libcst.Module([node.annotation.annotation]).code)
    self.variable_annotations.append(
        _VariableAnnotation(pos.start.line, pos.end.line, annotation))

  def _visit_decorators(self, node):
    if not node.decorators:
      return
    # The line range for this definition starts at the beginning of the last
    # decorator and ends at the definition's name.
    decorator = node.decorators[-1]
    start = self._get_position(decorator).start
    end = self._get_position(node.name).start
    self.decorators.append(_LineRange(start.line, end.line))

  def _visit_def(self, node):
    line = self._get_position(node).start.line
    if not self.defs_start or line < self.defs_start:
      self.defs_start = line

  def visit_ClassDef(self, node):
    self._visit_decorators(node)
    self._visit_def(node)

  def visit_FunctionDef(self, node):
    # A function signature's line range starts at the beginning of the signature
    # and ends at the final colon.
    self._add_structured_comment_group(
        self._get_position(node).start.line,
        self._get_position(node.whitespace_before_colon).end.line)
    self._visit_decorators(node)
    self._visit_def(node)


class Director:
  """Holds all of the directive information for a source file."""

  def __init__(self, src_tree, errorlog, filename, disable, code):
    """Create a Director for a source file.

    Args:
      src_tree:  The source text as a LibCST tree.
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
    # The docstring for unsafe_skip_copy says:
    #
    # When true, this skips the deep cloning of the module.
    # This can provide a small performance benefit, but you should only use this
    # if you know that there are no duplicate nodes in your tree (e.g. this
    # module came from the parser).
    #
    # We only pass in trees constructed by libcst.parse_module, so we disable
    # copying for the performance benefit.
    src_tree_with_metadata = libcst.metadata.MetadataWrapper(
        src_tree, unsafe_skip_copy=True)
    visitor = _ParseVisitor()
    try:
      src_tree_with_metadata.visit(visitor)
    except RecursionError:
      log.warning("File parsing failed. Comment directives and some variable "
                  "annotations will be ignored.")
      return
    if code:
      opcode_lines = _OpcodeLines.from_code(code)
    else:
      opcode_lines = None

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
                self._filename, comment.line, utils.message(e))

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
      self, line: int, data: str, open_ended: bool, line_range: _LineRange,
      opcode_lines: Optional[_OpcodeLines]):
    """Process a type: comment."""
    is_ignore = _IGNORE_RE.match(data)
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
      self, line: int, data: str, open_ended: bool, line_range: _LineRange,
      opcode_lines: Optional[_OpcodeLines]):
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

      def keep(error_name):
        if isinstance(line_range, _Attribute):
          return error_name == "attribute-error"
        elif isinstance(line_range, _Call):
          return error_name in _FUNCTION_CALL_ERRORS
        else:
          return True

      for error_name in values:
        if (error_name == _ALL_ERRORS or
            self._errorlog.is_valid_error_name(error_name)):
          if not keep(error_name):
            # Skip the directive if we are in a line range that is irrelevant to
            # it. (Every directive is also recorded in a base _LineRange that is
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
              self._filename, line, "Invalid error name: '%s'" % error_name)

  def _adjust_line_number_for_pytype_directive(
      self, line: int, error_class: str, line_range: _LineRange,
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
    # Treat line=0 as below the file, so we can filter it.
    line = error.lineno or sys.maxsize
    # Report the error if it isn't subject to any ignore or disable.
    return (line not in self._ignore and
            line not in self._disables[_ALL_ERRORS] and
            line not in self._disables[error.name])


def parse_src(src, python_version):
  """Parses a string of source code into a LibCST tree."""
  version_str = utils.format_version(python_version)
  if python_version >= (3, 9):
    log.warning("LibCST does not support Python %s; parsing with 3.8 instead.",
                version_str)
    version_str = "3.8"
  config = libcst.PartialParserConfig(python_version=version_str)
  return libcst.parse_module(src, config)
