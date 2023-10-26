"""Support for pattern matching."""

import collections
import enum

from typing import Dict, List, Optional, Set, Tuple, cast

from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.pyc import opcodes
from pytype.pytd import slots
from pytype.typegraph import cfg


# Type aliases

# Tri-state boolean for match case returns.
# True = always match, False = never match, None = sometimes match
_MatchSuccessType = Optional[bool]


class _MatchTypes(enum.Enum):
  """Track match types based on generated opcode."""

  CLASS = enum.auto()
  SEQUENCE = enum.auto()
  KEYS = enum.auto()
  MAPPING = enum.auto()
  CMP = enum.auto()

  @classmethod
  def make(cls, op: opcodes.Opcode):
    if op.name.startswith("MATCH_"):
      return cls[op.name[len("MATCH_"):]]
    else:
      return cls.CMP


class _Matches:
  """Tracks branches of match statements."""

  def __init__(self, ast_matches):
    self.start_to_end = {}
    self.end_to_starts = collections.defaultdict(list)
    self.match_cases = {}
    self.defaults = set()
    self.as_names = {}
    self.matches = []

    for m in ast_matches.matches:
      self._add_match(m.start, m.end, m.cases)

  def _add_match(self, start, end, cases):
    self.start_to_end[start] = end
    self.end_to_starts[end].append(start)
    for c in cases:
      for i in range(c.start, c.end + 1):
        self.match_cases[i] = start
      if c.is_underscore:
        self.defaults.add(c.start)
      if c.as_name:
        self.as_names[c.end] = c.as_name

  def __repr__(self):
    return f"""
      Matches: {sorted(self.start_to_end.items())}
      Cases: {self.match_cases}
      Defaults: {self.defaults}
    """


class _EnumTracker:
  """Track enum cases for exhaustiveness."""

  def __init__(self, enum_cls):
    self.enum_cls = enum_cls
    if isinstance(enum_cls, abstract.PyTDClass):
      # We don't construct a special class for pytd enums, so we have to get the
      # enum members manually here.
      self.members = []
      for k, v in enum_cls.members.items():
        if all(d.cls == enum_cls for d in v.data):
          self.members.append(f"{enum_cls.full_name}.{k}")
    else:
      self.members = list(enum_cls.get_enum_members(qualified=True))
    self.uncovered = set(self.members)
    # The last case in an exhaustive enum match always succeeds.
    self.implicit_default = None
    # Invalidate the tracker if we run into code that matches enums but is not a
    # simple match against a single enum value.
    self.is_valid = True

  def cover(self, enum_case):
    assert enum_case.cls == self.enum_cls
    self.uncovered.discard(enum_case.name)

  def cover_all(self):
    self.uncovered = set()

  def invalidate(self):
    self.is_valid = False


class _TypeTracker:
  """Track class type cases for exhaustiveness."""

  def __init__(self, match_var, ctx):
    self.match_var = match_var
    self.ctx = ctx
    self.could_contain_anything = False
    # Types of the current match var, as narrowed by preceding cases.
    self.types = []
    for d in match_var.data:
      if isinstance(d, abstract.Instance):
        self.types.append(d.cls)
      else:
        self.could_contain_anything = True
        break
    # Types of the current case var, as expanded by MATCH_CLASS opcodes
    self.case_types = collections.defaultdict(set)
    self.uncovered = set(self.types)

  def cover(self, line, case_var):
    for d in case_var.data:
      self.uncovered.discard(d)
      self.case_types[line].add(d)

  def cover_from_cmp(self, line, case_var):
    # If we compare `match_var == constant`, add the type of `constant` to the
    # current case so that instantiate_case_var can retrieve it.
    for d in case_var.data:
      self.case_types[line].add(d.cls)

  @property
  def complete(self):
    return not (self.uncovered or self.could_contain_anything)

  def get_narrowed_match_var(self, node):
    if self.could_contain_anything:
      return self.match_var.AssignToNewVariable(node)
    else:
      narrowed = [x.instantiate(node) for x in self.uncovered]
      return self.ctx.join_variables(node, narrowed)


class BranchTracker:
  """Track exhaustiveness in pattern matches."""

  def __init__(self, ast_matches, ctx):
    self.matches = _Matches(ast_matches)
    self._enum_tracker = {}
    self._type_tracker: Dict[int, Dict[int, _TypeTracker]] = (
        collections.defaultdict(dict))
    self._match_types: Dict[int, Set[_MatchTypes]] = (
        collections.defaultdict(set))
    self._active_ends = set()
    # If we analyse the same match statement twice, the second time around we
    # should not do exhaustiveness and redundancy checks since we have already
    # tracked all the case branches.
    self._seen_opcodes = set()
    self.ctx = ctx

  def _add_new_enum_match(self, match_val: abstract.Instance, match_line: int):
    self._enum_tracker[match_line] = _EnumTracker(match_val.cls)
    self._active_ends.add(self.matches.start_to_end[match_line])

  def _is_enum_match(
      self, match_val: abstract.BaseValue, case_val: abstract.BaseValue
  ) -> bool:
    if not (isinstance(match_val, abstract.Instance) and
            isinstance(match_val.cls, abstract.Class) and
            match_val.cls.is_enum):
      return False
    if not (isinstance(case_val, abstract.Instance) and
            case_val.cls == match_val.cls):
      return False
    return True

  def _get_enum_tracker(
      self, match_val: abstract.Instance, match_line: Optional[int]
  ) -> Optional[_EnumTracker]:
    """Get the enum tracker for a match line."""
    if match_line is None:
      return None
    if match_line not in self._enum_tracker:
      self._add_new_enum_match(match_val, match_line)
    enum_tracker = self._enum_tracker[match_line]
    if (match_val.cls != enum_tracker.enum_cls or
        self._match_types[match_line] != {_MatchTypes.CMP}):
      # We are matching a tuple or structure with different enums in it.
      enum_tracker.invalidate()
      return None
    return enum_tracker

  def _add_new_type_match(self, match_var: cfg.Variable, match_line: int):
    self._type_tracker[match_line][match_var.id] = _TypeTracker(
        match_var, self.ctx)

  def _make_instance_for_match(self, node, types):
    """Instantiate a type for match case narrowing."""
    # This specifically handles the case where we match against an
    # AnnotationContainer in MATCH_CLASS, and need to replace it with its base
    # class when narrowing the matched variable.
    ret = []
    for v in types:
      cls = v.base_cls if isinstance(v, abstract.AnnotationContainer) else v
      ret.append(self.ctx.vm.init_class(node, cls))
    return self.ctx.join_variables(node, ret)

  def instantiate_case_var(self, op, match_var, node):
    tracker = self.get_current_type_tracker(op, match_var)
    assert tracker is not None
    if tracker.case_types[op.line]:
      # We have matched on one or more classes in this case.
      return self._make_instance_for_match(node, tracker.case_types[op.line])
    else:
      # We have not matched on a type, just bound the current match var to a
      # variable.
      return tracker.get_narrowed_match_var(node)

  def _get_type_tracker(
      self, match_var: cfg.Variable, case_line: int
  ) -> _TypeTracker:
    match_line = self.matches.match_cases[case_line]
    if match_var.id not in self._type_tracker[match_line]:
      self._add_new_type_match(match_var, match_line)
    return self._type_tracker[match_line][match_var.id]

  def get_current_type_tracker(
      self, op: opcodes.Opcode, match_var: cfg.Variable
  ):
    line = self.get_current_match(op)
    return self._type_tracker[line].get(match_var.id)

  def get_current_type_trackers(self, op: opcodes.Opcode):
    line = self.get_current_match(op)
    return list(self._type_tracker[line].values())

  def get_current_match(self, op: opcodes.Opcode):
    match_line = self.matches.match_cases[op.line]
    return match_line

  def is_current_as_name(self, op: opcodes.Opcode, name: str):
    if op.line not in self.matches.match_cases:
      return None
    return self.matches.as_names.get(op.line) == name

  def register_match_type(self, op: opcodes.Opcode):
    if op.line not in self.matches.match_cases:
      return
    match_line = self.matches.match_cases[op.line]
    self._match_types[match_line].add(_MatchTypes.make(op))

  def _add_enum_branch(
      self,
      op: opcodes.Opcode,
      match_val: abstract.Instance,
      case_val: abstract.SimpleValue
  ) -> Optional[bool]:
    """Add a case branch for an enum match to the tracker."""
    if op in self._seen_opcodes:
      match_line = self.matches.match_cases.get(op.line)
      enum_tracker = self._get_enum_tracker(match_val, match_line)
      if not enum_tracker:
        return None
      if (enum_tracker.implicit_default and case_val and
          case_val.cls == enum_tracker.implicit_default.cls):
        return True
      else:
        return None
    else:
      self._seen_opcodes.add(op)
    match_line = self.matches.match_cases.get(op.line)
    enum_tracker = self._get_enum_tracker(match_val, match_line)
    if not enum_tracker or not enum_tracker.is_valid:
      return None
    if case_val.name in enum_tracker.uncovered:
      enum_tracker.cover(case_val)
      if enum_tracker.uncovered:
        return None
      else:
        # This is the last remaining case, and will always succeed.
        enum_tracker.implicit_default = case_val
        return True
    else:
      # This has already been covered, and will never succeed.
      return False

  def add_cmp_branch(self, op: opcodes.Opcode, match_var: cfg.Variable,
                     case_var: cfg.Variable) -> _MatchSuccessType:
    """Add a compare-based match case branch to the tracker."""
    try:
      case_val = abstract_utils.get_atomic_value(case_var)
    except abstract_utils.ConversionError:
      return None

    # If this is part of a case statement and the match includes class matching,
    # check if we need to include the compared value as a type case.
    # (We need to do this whether or not the match_var has a concrete value
    # because even an ambigious cmp match will require the type to be set within
    # the case branch).
    op = cast(opcodes.OpcodeWithArg, op)
    if (op.arg == slots.CMP_EQ and op.line in self.matches.match_cases):
      if tracker := self.get_current_type_tracker(op, match_var):
        tracker.cover_from_cmp(op.line, case_var)

    try:
      match_val = abstract_utils.get_atomic_value(match_var)
    except abstract_utils.ConversionError:
      return None
    if self._is_enum_match(match_val, case_val):
      return self._add_enum_branch(op, match_val, case_val)
    else:
      return None

  def add_class_branch(self, op: opcodes.Opcode, match_var: cfg.Variable,
                       case_var: cfg.Variable) -> _MatchSuccessType:
    """Add a class-based match case branch to the tracker."""
    type_tracker = self._get_type_tracker(match_var, op.line)
    type_tracker.cover(op.line, case_var)
    return type_tracker.complete or None

  def add_default_branch(self, op: opcodes.Opcode) -> _MatchSuccessType:
    """Add a default match case branch to the tracker."""
    match_line = self.matches.match_cases.get(op.line)
    if match_line is None:
      return None
    if match_line not in self._enum_tracker:
      return None
    self._enum_tracker[match_line].cover_all()
    return True

  def check_ending(self,
                   op: opcodes.Opcode,
                   implicit_return: bool = False) -> List[Tuple[int, Set[str]]]:
    """Check if we have ended a match statement with leftover cases."""
    if op.metadata.is_out_of_order:
      return []
    line = op.line
    if implicit_return:
      done = set()
      if line in self.matches.match_cases:
        start = self.matches.match_cases[line]
        end = self.matches.start_to_end[start]
        if end in self._active_ends:
          done.add(end)
    else:
      done = {i for i in self._active_ends if line > i}
    ret = []
    for i in done:
      for start in self.matches.end_to_starts[i]:
        tracker = self._enum_tracker[start]
        if tracker.is_valid:
          if uncovered := tracker.uncovered:
            ret.append((start, uncovered))
    self._active_ends -= done
    return ret
