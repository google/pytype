"""Explanation mechanism for cfgs."""

import sys

from pytype.typegraph import cfg


def LeaveOneOut(seq, pos):
  """Return a new list, with element at the given position removed."""
  return [v for i, v in enumerate(seq) if i != pos]


class Explainer(object):
  """Generate textual explanations for variable assignments.

  Attributes:
      program: The cfg.Program we're analyzing.
      cfg_node: Location in the program where this combination is analyzed.
      combination: A list of cfg.Binding instances.
      entrypoint: The program's entry point, or None.
      out: Output stream for printing
  """

  def __init__(self, program, entrypoint=None, out=None):
    self.program = program
    self.entrypoint = entrypoint or self.program.entrypoint
    self.out = out or sys.stdout

  def Explain(self, combination, cfg_node):
    """Print an explanation of why a combination is possible or not possible."""
    has_combination = cfg_node.HasCombination(combination)
    if has_combination:
      self.ExplainWhy(combination, cfg_node)
      return True
    else:
      self.ExplainWhyNot(combination, cfg_node)
      return False

  def ExplainWhy(self, combination, cfg_node):
    """Explain why a combination is possible."""
    self.out.write("At %s, we can have the following assignments:\n" %
                   cfg_node)
    self.DisplayPossible(combination, cfg_node)

  def DisplayPossible(self, combination, cfg_node):
    """Display a possible combination, together with program locations."""
    path = self.GetPath(combination, cfg_node)
    for v in combination:
      self.out.write("  v%d = %s" % (v.variable.id, repr(v.data)))
      self.out.write("  # Set at %s\n" % (
          self.GetLastAssignment(path, v).name))

  def ExplainWhyNot(self, combination, cfg_node):
    """Explain why a combination isn't possible."""

    # First, try to reduce the problem to a smaller set.
    for i in range(len(combination)):
      shortened = LeaveOneOut(combination, i)
      if not cfg_node.HasCombination(shortened):
        return self.ExplainWhyNot(shortened, cfg_node)

    # Do we have conflicting variables?
    conflicting_goals_str = self.ConflictingGoalsString(combination)
    if conflicting_goals_str:
      self.out.write(conflicting_goals_str)
      return

    # Is it just one assignment, which is impossible?
    if len(combination) == 1:
      v, = combination
      self.out.write("At %s, the assignment\n" % cfg_node)
      self.out.write("  v%d = %s\n" % (v.variable.id, repr(v.data)))
      self.out.write("is impossible for the following reason(s):\n")
      self.PrintBadSources(v, cfg_node)
      return

    # Is this combination possible except together with one value?
    # (This is always the case, because we know we were not able to reduce this
    #  problem to a smaller, still invalid, set of values above)
    for i in range(len(combination)):
      shortened = LeaveOneOut(combination, i)
      if cfg_node.HasCombination(shortened):
        bad_apple = combination[i]
        self.out.write("At %s, it's impossible that\n" % cfg_node)
        self.out.write("  v%d = %s\n" %
                       (bad_apple.variable.id, repr(bad_apple.data)))
        self.out.write("if we want this to be valid at the same time:\n")
        self.DisplayPossible(shortened, cfg_node)
        return

    # Can't happen.
    raise AssertionError("Internal error. Irreducible set without bad apple")

  def PrintBadSources(self, value, cfg_node):
    """Print sources we know are impossible."""
    blocked = self.GetBlocked([value], cfg_node)
    for new_cfg_node, source_sets in value.origins:
      if not self.CanReach(cfg_node, new_cfg_node, blocked):
        if self.CanReach(cfg_node, new_cfg_node, set()):
          n = None  # make pylint happy
          for n in self.FindPathBackwards(cfg_node, new_cfg_node):
            if n in blocked:
              break
          else:
            assert False, "Discrepancy between FindPathBackwards and CanReach"
          self.out.write("v%d from %s is overwritten at %s:\n" %
                         (value.variable.id, new_cfg_node, n))
          for v in value.variable.bindings:
            if v is not value and any(n == o.where for o in v.origins):
              self.out.write("v%d = %s\n" % (v.variable.id, v.data))
        else:
          self.out.write("The assignment at %s isn't reachable from %s.\n" %
                         (new_cfg_node, cfg_node))
        continue
      for source_set in source_sets:
        if new_cfg_node.HasCombination(list(source_set)):
          continue
        self.out.write("At %s, this:\n" % new_cfg_node)
        for v in source_set:
          self.out.write("  v%d = %s\n" % (v.variable.id, repr(v.data)))
        self.out.write("isn't possible because:\n")
        self.ExplainWhyNot(list(source_set), new_cfg_node)

  def ConflictingGoalsString(self, combination):
    """Print information about two variables overwriting each other."""
    variables = {}
    for value in combination:
      if value.variable in variables:
        variable = value.variable
        value1 = value
        value2 = variables[variable]
        return "\n".join([
            "Variable v%d can't be both" % variable.id,
            "  %s" % repr(value1.data),
            "and",
            "  %s" % repr(value2.data),
            "at the same time."])
      variables[value.variable] = value
    return None

  def FindPathBackwards(self, current, goal, seen=None):
    """Going through the call-flow graph backwards, return path to a goal.

    Args:
      current: Current CFG node.
      goal: Destination CFG node.
      seen: CFG nodes we have already visited. Will be modified.

    Returns:
      A path. (List of CFGNode)
    """
    if seen is None:
      seen = set()
    if current == goal:
      return [goal]
    if current in seen:
      return None
    seen.add(current)
    for node in current.incoming:
      path = self.FindPathBackwards(node, goal, seen)
      if path:
        return [current] + path
    return None

  def NodeReachable(self, node):
    """Return whether a CFG node is reachable from the program's entry point."""
    if not self.entrypoint:
      return True
    return self.FindPathBackwards(node, self.entrypoint, set()) is not None

  def GetLastAssignment(self, path, value):
    """Given a variable assignment and a path, return the latest assignment."""
    nodes = {cfg_node for cfg_node, _ in value.origins}
    for node in reversed(path):
      if node in nodes:
        return node
    raise ValueError("Node not in path")

  def GetBlocked(self, combination, current_node):
    """Get all cfg nodes where anything in a combination is assigned."""
    blocked = set()
    for value in combination:
      for other_value in value.variable.bindings:
        for node, _ in other_value.origins:
          blocked.add(node)
    if current_node in blocked:
      blocked.remove(current_node)
    return blocked

  def CanReach(self, start, end, blocked):
    """Check if two nodes are connected, taking blocked nodes into account."""
    return self.FindPathBackwards(start, end, blocked.copy())

  def ExpandGoal(self, combination, goal, source_set):
    """Given a list of values, expand one goal by its sources."""
    new_combination = set(combination)
    new_combination.remove(goal)
    new_combination.update(source_set)
    return list(new_combination)

  def Str(self, thing):
    """Helper function for debugging."""
    if isinstance(thing, list):
      return "\n".join(self.Str(v) for v in thing) + "\n"
    elif isinstance(thing, cfg.Binding):
      return "v%d = %s" % (thing.variable.id, repr(thing.data))

  def GetPath(self, combination, cfg_node):
    """Given a combination, find the corresponding path through the program."""
    if not combination:
      # No more goals. We're done.
      if self.entrypoint:
        if not self.FindPathBackwards(cfg_node, self.entrypoint, set()):
          return None
        else:
          return [self.entrypoint, cfg_node]
      else:
        return [cfg_node]
    if self.ConflictingGoalsString(combination):
      return None
    blocked = self.GetBlocked(combination, cfg_node)
    for goal in combination:
      for new_cfg_node, source_sets in goal.origins:
        if self.CanReach(cfg_node, new_cfg_node, blocked):
          for source_set in source_sets:
            new_combination = self.ExpandGoal(combination, goal, source_set)
            path_start = self.GetPath(new_combination, new_cfg_node)
            if path_start is not None:
              return path_start + [cfg_node]
    return None


def Explain(combination, cfg_node, entrypoint=None, out=None):
  """Print an explanation of why a combination is possible or not possible.

     This reproduces (and uses) the logic of the cfg C extension module,
     but prints out additional information about why and where.

  Arguments:
    combination: A combination of variable values.
    cfg_node: Where we are in the program.
    entrypoint: Entry point to the program, or None.
    out: Stream for printing.

  Returns:
    A boolean with the same value as cfg.CFGNode.HasCombination(...)
  """
  program = cfg_node.program
  return Explainer(program, entrypoint, out).Explain(combination, cfg_node)
