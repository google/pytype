"""Points-to / dataflow / cfg graph engine.

It can be used to run reaching-definition queries on a nested CFG graph
and to model path-specific visibility of nested data structures.
"""


import collections


class Program(object):
  """Program instances describe program entities.

  This class ties together the CFG, the data flow graph (variables + values) as
  well as methods. We use this for issuing IDs: We need every CFG node to have a
  unique ID, and this class does the corresponding counting.

  Attributes:
    entrypoint: Entrypoint of the program, if it has one. (None otherwise)
    cfg_nodes: CFG nodes in use. Will be used for assigning node IDs.
    variables: Variables in use. Will be used for assigning variable IDs.
  """

  def __init__(self):
    """Initialize a new (initially empty) program."""
    self.entrypoint = None
    self.cfg_nodes = []
    self.variables = []

  def NewCFGNode(self, name=None):
    """Start a new CFG node."""
    cfg_node = CFGNode(self, name, len(self.cfg_nodes))
    self.cfg_nodes.append(cfg_node)
    return cfg_node

  def NewVariable(self, name, values=None, source_set=None, where=None):
    """Create a new Variable.

    A Variable typically models a "union type", i.e., a disjunction of different
    possible types.  This constructor assumes that all the values in this
    Variable have the same origin(s). If that's not the case, construct a
    variable with values=[] and origins=[] and then call AddValue() to add the
    different values.

    Arguments:
      name: Name of the variable. For logging. Doesn't need to be unique.
      values: Optionally, a sequence of possible values this variable can have.
      source_set: If we have values, the source_set they depend on. An instance
        of SourceSet.
      where: Where in the CFG this node is assigned.

    Returns:
      A Variable instance.
    """
    variable = Variable(self, name, len(self.variables))
    self.variables.append(variable)
    if values is not None:
      assert source_set is not None and where is not None
      for data in values:
        value = variable.AddValue(data)
        value.AddOrigin(where, source_set)
    return variable


class CFGNode(object):
  """A node in the CFG.

  Assignments within one CFG node are treated as unordered: E.g. if "x = x + 1"
  is in a single CFG node, both values for x will be visible from inside that
  node.

  Attributes:
    program: The Program instance we belong to
    id: Numberical node id.
    name: Name of this CFGNode, or None. For debugging.
    incoming: Other CFGNodes that are connected to this node.
    outgoing: CFGNodes we connect to.
    values: Values that are being assigned to Variables at this CFGNode.
  """
  __slots__ = ("program", "id", "name", "incoming", "outgoing", "values")

  def __init__(self, program, name, cfgnode_id):
    """Initialize a new CFG node. Called from Program.NewCFGNode."""
    self.program = program
    self.id = cfgnode_id
    self.name = name
    self.incoming = set()
    self.outgoing = set()
    self.values = set()  # filled through RegisterValue()

  def ConnectNew(self, name=None):
    """Add a new node connected to this node."""
    cfg_node = self.program.NewCFGNode(name)
    self.ConnectTo(cfg_node)
    return cfg_node

  def ConnectTo(self, cfg_node):
    """Connect this node to an existing node."""
    self.outgoing.add(cfg_node)
    cfg_node.incoming.add(self)

  def HasCombination(self, values):
    """Query whether a combination is possible.

    Query whether its possible to have the given combination of values at
    this CFG node (I.e., whether they can all be assigned at the same time.)
    This will e.g. tell us whether a return value is possible given a specific
    combination of argument values.

    Arguments:
      values: A list of Values
    Returns:
      True if the combination is possible, False otherwise.
    """
    return Solver(self.program, values, self, self.program.entrypoint).Solve()

  def RegisterValue(self, value):
    self.values.add(value)


class SourceSet(frozenset):
  """A SourceSet is a combination of Values that was used to form a Value.

  In this context, a "source" is a Value that was used to create another Value.
  E.g., for a statement like "z = a.x + y", a, a.x and y would be the
  Sources to create z, and would form a SourceSet.
  """
  __slots__ = ()


class Origin(collections.namedtuple("_", "where, source_sets")):
  """An "origin" is an explanation of how a value was constructed.

  It consists of a CFG node and a set of sourcesets.

  Attributes:
    where: The CFG node where this assignment happened.
    source_sets: Possible SourceSets used to construct the value we belong to.
      A set of SourceSet instances.
  """
  __slots__ = ()

  def __new__(cls, where, source_sets=None):
    return super(Origin, cls).__new__(
        cls, where, source_sets or set())

  def AddSourceSet(self, source_set):
    """Add a new possible source set."""
    self.source_sets.add(SourceSet(source_set))


class Value(object):
  """A Value assigns a value to a (specific) variable.

  Values will therefore be stored in a dictionary in the Variable class, mapping
  strings to Value instances.
  Depending on context, a Value might also be called a "Source" (if it's
  used for creating another value) or a "goal" (if we want to find a solution
  for a path through the program that assigns it).

  A value has history ("origins"): It knows where the value was
  originally retrieved from, before being assigned to something else here.
  Origins contain, through source_sets, "sources", which are other values.
  """
  __slots__ = ("program", "variable", "origins", "data", "_cfgnode_to_origin")

  def __init__(self, program, variable, data):
    """Initialize a new Value. Usually called through Variable.AddValue."""
    self.program = program
    self.variable = variable
    self.origins = []
    self.data = data
    self._cfgnode_to_origin = {}

  def IsVisible(self, viewpoint):
    """Can we "see" this value from the current cfg node?

    This will run a solver to determine whether there's a path through the
    program that makes our variable have this value at the given CFG node.

    Arguments:
      viewpoint: The CFG node at which this value is possible / not possible.

    Returns:
      True if there is at least one path through the program
      in which the value was assigned (and not overwritten afterwards), and all
      the values it depends on were assigned (and not overwritten) before that,
      etc.
    """
    solver = Solver(self.program, {self}, viewpoint, self.program.entrypoint)
    return solver.Solve()

  def _FindOrAddOrigin(self, cfg_node):
    try:
      origin = self._cfgnode_to_origin[cfg_node]
    except KeyError:
      origin = Origin(cfg_node)
      self.origins.append(origin)
      self._cfgnode_to_origin[cfg_node] = origin
      self.variable.RegisterValueAtNode(self, cfg_node)
      cfg_node.RegisterValue(self)
    return origin

  def FindOrigin(self, cfg_node):
    """Return an Origin instance for a CFGNode, or None."""
    return self._cfgnode_to_origin.get(cfg_node)

  def AddOrigin(self, where, source_set):
    """Add another possible origin to this value."""
    origin = self._FindOrAddOrigin(where)
    origin.AddSourceSet(source_set)

  def AssignToNewVariable(self, name, where):
    """Assign this value to a new variable."""
    variable = self.program.NewVariable(name)
    value = variable.AddValue(self.data)
    value.AddOrigin(where, {self})
    return variable


class Variable(object):
  """A Variable, together with all the values it can possibly have."""
  __slots__ = ("program", "name", "id", "_data_id_to_value",
               "_cfgnode_to_values")

  def __init__(self, program, name, variable_id):
    """Initialize a new Variable. Called through Program.NewVariable."""
    self.program = program
    self.name = name
    self.id = variable_id
    self._data_id_to_value = {}
    self._cfgnode_to_values = collections.defaultdict(set)

  def __repr__(self):
    return "<Variable %d \"%s\": %d choices>" % (
        self.id, self.name, len(self.values))

  __str__ = __repr__

  def Values(self, viewpoint):
    """Filters down the possibilities of values for this variable.

    It determines this by analyzing the control flow graph. Any definition for
    this variable that is invisible from the current point in the CFG is
    filtered out. This function differs from Filter() in that it only honors the
    CFG, not the source sets. As such, it's much faster.

    Arguments:
      viewpoint: The CFG node at which to determine the possible values.

    Returns:
      A filtered list of values for this variable.
    """
    result = set()
    seen = set()
    stack = [viewpoint]
    while stack:
      node = stack.pop()
      seen.add(node)
      # _cfgnode_to_values is a defaultdict, so don't use "get"
      if node in self._cfgnode_to_values:
        values = self._cfgnode_to_values[node]
        assert values, "empty value list"
        result.update(values)
        # Don't expand this node - previous assignments to this variable will
        # be invisible, since they're overwritten here.
        continue
      else:
        stack.extend(set(node.incoming) - seen)
    return result

  def Data(self, viewpoint):
    """Like Values(cfg_node), but only return the data."""
    return [value.data for value in self.Values(viewpoint)]

  def Filter(self, viewpoint):
    """Filters down the possibilities of this variable.

    It analyzes the control flow graph. Any definition for this variable that is
    impossible at the current point in the CFG is filtered out.

    Arguments:
      viewpoint: The CFG node at which to determine the possible values.

    Returns:
      A filtered list of values for this variable.
    """
    return [value for value in self.values if value.IsVisible(viewpoint)]

  def FilteredData(self, viewpoint):
    """Like Filter(viewpoint), but only return the data."""
    return [value.data for value in self.values if value.IsVisible(viewpoint)]

  def _FindOrAddValue(self, data):
    try:
      value = self._data_id_to_value[id(data)]
    except KeyError:
      value = Value(self.program, self, data)
      self._data_id_to_value[id(data)] = value
    return value

  def AddValue(self, data, source_set=None, where=None):
    """Add another choice to this variable.

    This will not overwrite this variable in the current CFG node - do that
    explicitly with RemoveChoicesFromCFGNode.  (It's legitimate to have multiple
    values for a variable on the same CFG node, e.g. if a union type is
    introduced at that node)

    Arguments:
      data: A user specified object to uniquely identify this value.
      source_set: An instance of SourceSet, i.e. a set of instances of Origin.
      where: Where in the CFG this variable was assigned to this value.

    Returns:
      The new value.
    """
    value = self._FindOrAddValue(data)
    if source_set or where:
      assert source_set is not None and where is not None
      value.AddOrigin(where, source_set)
    return value

  def AddValues(self, variable, where):
    """Adds all the values from another variable to this one."""
    for value in variable.values:
      copy = self.AddValue(value.data)
      copy.AddOrigin(where, {value})

  def AssignToNewVariable(self, name, where):
    """Assign this variable to a new variable.

    This is essentially a copy: All entries in the Union will be copied to
    the new variable, but with the corresponding current variable value
    as an origin.

    Arguments:
      name: Name of the new variable.
      where: CFG node where the assignment happens.

    Returns:
      A new variable.
    """
    new_variable = self.program.NewVariable(name)
    for value in self.values:
      new_value = new_variable.AddValue(value.data)
      new_value.AddOrigin(where, {value})
    return new_variable

  def RegisterValueAtNode(self, value, node):
    self._cfgnode_to_values[node].add(value)

  @property
  def values(self):
    return self._data_id_to_value.values()

  @property
  def data(self):
    return [value.data for value in self.values]


class State(object):
  """A state needs to "solve" a list of goals to succeed.

  Attributes:
    pos: Our current position in the CFG.
    goals: A list of values we'd like to be valid at this position.
  """
  __slots__ = ("pos", "goals")

  def __init__(self, pos, goals):
    """Initialize a state that starts at the given cfg node."""
    assert all(isinstance(goal, Value) for goal in goals)
    self.pos = pos
    self.goals = set(goals)  # Make a copy. We modify these.

  def Done(self):
    """Is this State solved? This checks whether the list of goals is empty."""
    return not self.goals

  def HasConflictingGoals(self):
    """Are there values in this state that can't be valid at the same time?

    Returns:
      True if we would we need a variable to be assigned to two distinct
      values at the same time in order to solve this state. False if there are
      no conflicting goals.

    Raises:
      AssertionError: For internal errors.
    """
    variables = {}
    for goal in self.goals:
      if goal.variable in variables:
        if variables[goal.variable] == goal:
          raise AssertionError("Internal error. Duplicate goal.")
        # TODO(kramm): What if existing->value == goal->value ?
        return True
      variables[goal.variable] = goal
    return False

  def NodesWithAssignments(self):
    """Find all CFG nodes corresponding to goal variable assignments.

    Mark all nodes that assign any of the goal variables (even to values not
    specified in goals).  This is used to "block" all cfg nodes that are
    conflicting assignments for the set of values in state.

    Returns:
      A set of instances of CFGNode. At every CFGNode in this set, at least
      one variable in the list of goals is assigned to something.
    """
    return set(origin.where
               for goal in self.goals
               for other_value in goal.variable.values
               for origin in other_value.origins)

  def Replace(self, goal, replace_with):
    """Replace a goal with new goals (the origins of the expanded goal)."""
    assert goal in self.goals, "goal to expand not in state"
    self.goals.remove(goal)
    self.goals.update(replace_with)

  def RemoveFinishedGoals(self):
    """Remove all goals that are trivially fulfilled at the current CFG node."""
    seen_goals = set()
    # We might remove multiple layers of nested goals, so loop until we don't
    # find anything to replace anymore.
    changed = True
    while changed:
      changed = False
      for goal in self.goals:
        if goal in seen_goals:
          # Only process a given goal once, to prevent infinite loops for cyclic
          # data structures.
          continue
        seen_goals.add(goal)
        origin = goal.FindOrigin(self.pos)
        # For source sets > 2, we don't know which sources to use, so we have
        # to let the solver iterate over them later.
        if origin and len(origin.source_sets) <= 1:
          source_set, = origin.source_sets  # we always have at least one.
          self.goals.remove(goal)
          self.goals.update(source_set)
          changed = True
          break

  def __hash__(self):
    """Compute hash for this State. We use States as keys when memoizing."""
    return hash(self.pos) + hash(frozenset(self.goals))

  def __eq__(self, other):
    return self.pos == other.pos and self.goals == other.goals

  def __ne__(self, other):
    return not self == other


def _FindNodeBackwards(start, finish, seen):
  """Determine whether we can reach a CFG node, going backwards.

  Traverse the CFG from a starting point to find a given node, but avoid any
  nodes marked as "seen" (either because we have actually already seen them, or
  because they were disabled beforehand).

  Arguments:
    start: Start node.
    finish: Node we're looking for.
    seen: A set of node we've already seen. This set is modified.

  Returns:
    True if we can find this node, False otherwise. If this function returns
    False, the seen set will contain all nodes reachable from the start node.
  """
  stack = [start]
  while stack:
    node = stack.pop()
    if node in seen:
      # The "finish" node is always in seen, as we insert all "variable"
      # (which includes its parent value) into it.
      if node is finish:
        return True
      continue
    seen.add(node)
    stack.extend(node.incoming)
  return False


def _AllValuesAreReachable(value, reachable_nodes, seen_values=None):
  """Check whether we can reach a value using a subset of the CFG.

  Check whether the reachable nodes contain all the values and, recursively,
  their origins. This is used for quickly checking whether a solution can exist.

  Arguments:
    value: Value to start with.
    reachable_nodes: A set of nodes we can reach.
    seen_values: Optional: Values we have already seen. Will be modified.

  Returns:
    True if we can reach this value and all its dependencies, False otherwise.
  """
  if seen_values is None:
    seen_values = set()
  if value in seen_values:
    return True
  seen_values.add(value)

  for origin in value.origins:
    if origin.where not in reachable_nodes:
      continue
    for source_set in origin.source_sets:
      if all(_AllValuesAreReachable(source, reachable_nodes, seen_values)
             for source in source_set):
        return True
  return False


class Solver(object):
  """The solver class is instantiated for a given "problem" instance.

  It maintains a cache of solutions for subproblems to be able to recall them if
  they reoccur in the solving process.
  """

  def __init__(self, program, start_attrs, start_node, end_node):
    """Initialize a solver instance. Every instance has their own cache.

    Initialize a solver that tries to prove one or more values starting (and
    going backwards from) a given node, all the way to (optionally) an end
    node.

    Arguments:
      program: The program we're in.
      start_attrs: The assignments we're trying to have, at the start_node.
      start_node: The CFG node where we want the assignments to be active.
      end_node: The entry point of the program. (The solver goes through the
        CFG backwards, hence the entry point is at the "end")
    """
    self.program = program
    self.start_attrs = start_attrs
    self.start_node = start_node
    self.end_node = end_node
    self._solved_states = {}

  def Solve(self):
    """Try to solve the problem Solver was initialized with.

    Returns:
      True if there is a path through the program that would give "start_attr"
      its value at the "start_node" program position. For larger programs, this
      might only look for a partial path (i.e., a path that doesn't go back all
      the way to the entry point of the program).
    """
    if not self.CanHaveSolution():
      return False
    state = State(self.start_node, self.start_attrs)
    return self._RecallOrFindSolution(state)

  def _RecallOrFindSolution(self, state):
    """Memoized version of FindSolution()."""
    if state in self._solved_states:
      return self._solved_states[state]

    # To prevent infinite loops, we insert this state into the hashmap as a
    # solvable state, even though we have not solved it yet. The reasoning is
    # that if it's possible to solve this state at this level of the tree, it
    # can also be solved in any of the children.
    self._solved_states[state] = True

    result = self._solved_states[state] = self._FindSolution(state)
    return result

  def CanHaveSolution(self):
    """Do a quick (one DFS run) sanity check of whether a solution can exist."""
    reachable = set()
    _FindNodeBackwards(self.start_node, None, reachable)  # populate reachable
    for value in self.start_attrs:
      if not _AllValuesAreReachable(value, reachable):
        return False
    return True

  def _FindSolution(self, state):
    """Find a sequence of assignments that would solve the given state."""
    if state.Done():
      return True
    if state.HasConflictingGoals():
      return False
    blocked = state.NodesWithAssignments()
    # We don't treat our current CFG node as blocked: If one of the goal
    # variables is overwritten by an assignment at our current pos, we assume
    # that assignment can still see the previous values.
    blocked.discard(state.pos)
    # Find the goal cfg node that was assigned last.  Due to the fact that we
    # treat CFGs as DAGs, there's typically one unique cfg node with this
    # property.
    for goal in state.goals:
      # "goal" is the assignment we're trying to find.
      for origin in goal.origins:
        # Copy the set, to re-use it for remembering which nodes we visited
        # so far. This is expensive, but typically not as expensive as
        # rerunning NodesWithAssignments.
        seen = blocked.copy()
        seen.add(origin.where)
        if _FindNodeBackwards(state.pos, origin.where, seen):
          # This loop over multiple different combinations of origins is why
          # we need memoization of states.
          for source_set in origin.source_sets:
            new_state = State(origin.where, state.goals)
            new_state.Replace(goal, source_set)
            # Also remove all goals that are trivially fulfilled at the
            # new CFG node.
            new_state.RemoveFinishedGoals()
            if not source_set and self.end_node:
              # If we reached a value without further dependencies, check
              # whether the corresponding cfg node is reachable from the entry
              # point of the program.
              seen = {self.end_node}
              if not _FindNodeBackwards(new_state.pos, self.end_node, seen):
                continue
            if self._RecallOrFindSolution(new_state):
              return True
    return False

