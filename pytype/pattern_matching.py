"""Support for pattern matching."""

import collections
import enum

from typing import Dict, List, Optional, Set, Tuple, Union, cast

from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.pyc import opcodes
from pytype.pytd import slots
from pytype.typegraph import cfg


# Type aliases

# Tri-state boolean for match case returns.
# True = always match, False = never match, None = sometimes match
_MatchSuccessType = Optional[bool]

# Value held in an Option; enum members are stored as strings
_Value = Union[str, abstract.BaseValue]


def _get_class_values(cls: abstract.Class) -> Optional[List[_Value]]:
  """Get values for a class with a finite set of instances."""
  if not isinstance(cls, abstract.Class):
    return None
  if cls.is_enum:
    return _get_enum_members(cls)
  else:
    return None


def _get_enum_members(enum_cls: abstract.Class) -> List[str]:
  """Get members of an enum class."""
  if isinstance(enum_cls, abstract.PyTDClass):
    # We don't construct a special class for pytd enums, so we have to get the
    # enum members manually here.
    members = []
    for k, v in enum_cls.members.items():
      if all(d.cls == enum_cls for d in v.data):
        members.append(f"{enum_cls.full_name}.{k}")
    return members
  else:
    return list(enum_cls.get_enum_members(qualified=True))


class _Option:
  """Holds a match type option and any associated values."""

  def __init__(self, typ=None):
    self.typ: abstract.BaseValue = typ
    self.values: Set[_Value] = set()
    self.indefinite: bool = False

  @property
  def is_empty(self) -> bool:
    return not(self.values or self.indefinite)


class _OptionSet:
  """Holds a set of options."""

  def __init__(self):
    # Collection of options, stored as a dict rather than a set so we can find a
    # given option efficiently.
    self._options: Dict[abstract.Class, _Option] = {}

  def __iter__(self):
    yield from self._options.values()

  def __bool__(self):
    return not self.is_complete

  @property
  def is_complete(self) -> bool:
    return all(x.is_empty for x in self)

  def add_instance(self, val):
    """Add an instance to the match options."""
    cls = val.cls
    if cls not in self._options:
      self._options[cls] = _Option(cls)
    if isinstance(val, abstract.ConcreteValue):
      self._options[cls].values.add(val)
    else:
      self._options[cls].indefinite = True

  def add_type(self, cls):
    """Add an class to the match options."""
    if cls not in self._options:
      self._options[cls] = _Option(cls)
    vals = _get_class_values(cls)
    if vals is not None:
      self._options[cls].values |= vals
    else:
      self._options[cls].indefinite = True

  def cover_instance(self, val) -> List[_Value]:
    """Remove an instance from the match options."""
    cls = val.cls
    if cls not in self._options:
      return []
    opt = self._options[cls]
    if val in opt.values:
      opt.values.remove(val)
      return [val]
    else:
      return []

  def cover_type(self, val) -> List[_Value]:
    """Remove a class and any associated instances from the match options."""
    if val not in self._options:
      return []
    opt = self._options[val]
    vals = list(opt.values)
    opt.values = set()
    if opt.indefinite:
      # opt is now empty; we have covered all potential values
      opt.indefinite = False
      return [val]
    else:
      return vals


class _OptionTracker:
  """Tracks a set of match options."""

  def __init__(self, match_var, ctx):
    self.match_var: cfg.Variable = match_var
    self.ctx = ctx
    self.options: _OptionSet = _OptionSet()
    self.could_contain_anything: bool = False
    # The types of the match var within each case branch
    self.cases: Dict[int, _OptionSet] = collections.defaultdict(_OptionSet)
    # The last case in an exhaustive match always succeeds.
    self.implicit_default: Optional[abstract.BaseValue] = None
    self.is_valid: bool = True

    for d in match_var.data:
      if isinstance(d, abstract.Instance):
        self.options.add_instance(d)
      else:
        self.options.add_type(d)

  @property
  def is_complete(self) -> bool:
    return self.options.is_complete

  def get_narrowed_match_var(self, node) -> cfg.Variable:
    if self.could_contain_anything:
      return self.match_var.AssignToNewVariable(node)
    else:
      narrowed = []
      for opt in self.options:
        if not opt.is_empty:
          narrowed.append(opt.typ.instantiate(node))
      return self.ctx.join_variables(node, narrowed)

  def cover(self, line, var) -> List[_Value]:
    ret = []
    for d in var.data:
      if isinstance(d, abstract.Instance):
        ret += self.options.cover_instance(d)
        self.cases[line].add_instance(d)
      else:
        ret += self.options.cover_type(d)
        self.cases[line].add_type(d)
    return ret

  def cover_from_cmp(self, line, case_var) -> List[_Value]:
    ret = []
    # If we compare `match_var == constant`, add the type of `constant` to the
    # current case so that instantiate_case_var can retrieve it.
    for d in case_var.data:
      ret += self.options.cover_instance(d)
      self.cases[line].add_instance(d)
      if isinstance(d, abstract.ConcreteValue) and d.pyval is None:
        # Need to special-case `case None` since it's compiled differently.
        ret += self.options.cover_type(d.cls)
    return ret

  def cover_from_none(self, line) -> List[_Value]:
    cls = self.ctx.convert.none_type
    self.cases[line].add_type(cls)
    return self.options.cover_type(cls)

  def invalidate(self):
    self.is_valid = False


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
    self.members = _get_enum_members(enum_cls)
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


class _LiteralTracker:
  """Track literal cases for exhaustiveness."""

  def __init__(self, match_var):
    self.match_var = match_var
    self.members = [x.pyval for x in match_var.data]
    self.uncovered = set(self.members)
    # The last case in an exhaustive match always succeeds.
    self.implicit_default = None
    # Invalidate the tracker if we run into code that is not a simple match
    # against a single value.
    self.is_valid = True

  def cover(self, literal_case):
    self.uncovered.discard(literal_case.pyval)

  def cover_all(self):
    self.uncovered = set()

  def invalidate(self):
    self.is_valid = False


class BranchTracker:
  """Track exhaustiveness in pattern matches."""

  def __init__(self, ast_matches, ctx):
    self.matches = _Matches(ast_matches)
    self._enum_tracker = {}
    self._literal_tracker = {}
    self._option_tracker: Dict[int, Dict[int, _OptionTracker]] = (
        collections.defaultdict(dict))
    self._match_types: Dict[int, Set[_MatchTypes]] = (
        collections.defaultdict(set))
    self._active_ends = set()
    # If we analyse the same match statement twice, the second time around we
    # should not do exhaustiveness and redundancy checks since we have already
    # tracked all the case branches.
    self._seen_opcodes = set()
    self.ctx = ctx

  def _get_option_tracker(
      self, match_var: cfg.Variable, case_line: int
  ) -> _OptionTracker:
    """Get the option tracker for a match line."""
    match_line = self.matches.match_cases[case_line]
    if (match_line not in self._option_tracker or
        match_var.id not in self._option_tracker[match_line]):
      self._option_tracker[match_line][match_var.id] = (
          _OptionTracker(match_var, self.ctx))
    return self._option_tracker[match_line][match_var.id]

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

  def _get_literal_tracker(
      self, match_var: cfg.Variable, match_line: Optional[int]
  ) -> Optional[_LiteralTracker]:
    """Get the literal tracker for a match line."""
    if match_line is None:
      return None
    if match_line not in self._literal_tracker:
      self._add_new_literal_match(match_var, match_line)
    literal_tracker = self._literal_tracker[match_line]
    if (match_var.id != literal_tracker.match_var.id or
        self._match_types[match_line] != {_MatchTypes.CMP}):
      # We are matching a tuple or structure with different literals in it.
      literal_tracker.invalidate()
      return None
    return literal_tracker

  def _is_literal_match(
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

  def _add_new_literal_match(self, match_var: cfg.Variable, match_line: int):
    self._literal_tracker[match_line] = _LiteralTracker(match_var)
    self._active_ends.add(self.matches.start_to_end[match_line])

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
    tracker = self._get_option_tracker(match_var, op.line)
    if tracker.cases[op.line]:
      # We have matched on one or more classes in this case.
      types = [x.typ for x in tracker.cases[op.line]]
      return self._make_instance_for_match(node, types)
    else:
      # We have not matched on a type, just bound the current match var to a
      # variable.
      return tracker.get_narrowed_match_var(node)

  def get_current_type_tracker(
      self, op: opcodes.Opcode, match_var: cfg.Variable
  ):
    line = self.get_current_match(op)
    return self._option_tracker[line].get(match_var.id)

  def get_current_type_trackers(self, op: opcodes.Opcode):
    line = self.get_current_match(op)
    return list(self._option_tracker[line].values())

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

  def _add_literal_branch(
      self,
      op: opcodes.Opcode,
      match_var: cfg.Variable,
      case_val: abstract.SimpleValue
  ) -> Optional[bool]:
    """Add a case branch for a literal match to the tracker."""
    if op in self._seen_opcodes:
      match_line = self.matches.match_cases.get(op.line)
      tracker = self._get_literal_tracker(match_var, match_line)
      if not tracker:
        return None
      if (tracker.implicit_default and case_val and
          case_val.cls == tracker.implicit_default.cls):
        return True
      else:
        return None
    else:
      self._seen_opcodes.add(op)
    match_line = self.matches.match_cases.get(op.line)
    tracker = self._get_literal_tracker(match_var, match_line)
    if not tracker or not tracker.is_valid:
      return None
    if not isinstance(case_val, abstract.ConcreteValue):
      tracker.invalidate()
      return None
    if case_val.pyval in tracker.uncovered:
      tracker.cover(case_val)
      if tracker.uncovered:
        return None
      else:
        # This is the last remaining case, and will always succeed.
        tracker.implicit_default = case_val
        return True
    else:
      # This has already been covered, and will never succeed.
      return False

  def add_none_branch(self, op: opcodes.Opcode, match_var: cfg.Variable):
    if op.line in self.matches.match_cases:
      if tracker := self.get_current_type_tracker(op, match_var):
        tracker.cover_from_none(op.line)
        if not tracker.is_complete:
          return None
        else:
          # This is the last remaining case, and will always succeed.
          tracker.implicit_default = self.ctx.convert.none_type
          return True

  def add_cmp_branch(
      self,
      op: opcodes.OpcodeWithArg,
      cmp_type: int,
      match_var: cfg.Variable,
      case_var: cfg.Variable
  ) -> _MatchSuccessType:
    """Add a compare-based match case branch to the tracker."""
    if cmp_type not in (slots.CMP_EQ, slots.CMP_IS):
      return None

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
    if op.line in self.matches.match_cases:
      if tracker := self.get_current_type_tracker(op, match_var):
        tracker.cover_from_cmp(op.line, case_var)
        if not tracker.is_complete:
          return None
        else:
          # This is the last remaining case, and will always succeed.
          tracker.implicit_default = case_val
          return True

    if all(isinstance(x, abstract.ConcreteValue) for x in match_var.data):
      # We are matching a union of concrete values, i.e. a Literal
      return self._add_literal_branch(op, match_var, case_val)

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
    tracker = self._get_option_tracker(match_var, op.line)
    tracker.cover(op.line, case_var)
    return tracker.is_complete or None

  def add_default_branch(self, op: opcodes.Opcode) -> _MatchSuccessType:
    """Add a default match case branch to the tracker."""
    match_line = self.matches.match_cases.get(op.line)
    if match_line is None:
      return None
    if match_line in self._enum_tracker:
      self._enum_tracker[match_line].cover_all()
    elif match_line in self._literal_tracker:
      self._literal_tracker[match_line].cover_all()
    else:
      return None
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
        if start in self._enum_tracker:
          tracker = self._enum_tracker[start]
        elif start in self._literal_tracker:
          tracker = self._literal_tracker[start]
        else:
          # We have nested matches, one of which is not an enum
          continue
        if tracker.is_valid:
          if uncovered := tracker.uncovered:
            ret.append((start, uncovered))
    self._active_ends -= done
    return ret
