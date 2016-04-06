"""Points-to / dataflow / cfg graph engine.

It can be used to run reaching-definition queries on a nested CFG graph
and to model path-specific visibility of nested data structures.
"""


import collections


from pytype.pytd import utils


_solved_find_queries = {}
_supernode_reachable = {}


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
    self.next_variable_id = 0
    self.solver = None

  def NewCFGNode(self, name=None):
    """Start a new CFG node."""
    cfg_node = CFGNode(self, name, len(self.cfg_nodes))
    self.cfg_nodes.append(cfg_node)
    return cfg_node

  @property
  def variables(self):
    return {value.variable for node in self.cfg_nodes for value in node.values}

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
      source_set: If we have values, the source_set they all depend on. An
        instance of SourceSet.
      where: Where in the CFG this node is assigned.

    Returns:
      A Variable instance.
    """
    variable = Variable(self, name, self.next_variable_id)
    self.next_variable_id += 1
    if values is not None:
      assert source_set is not None and where is not None
      for data in values:
        value = variable.AddValue(data)
        value.AddOrigin(where, source_set)
    return variable

  def Freeze(self):
    """'Freeze' the program in preparation for solving.

    At this point, the graph must have an entrypoint and every node must be
    reachable (going forwards) from it, in order for _CompressGraph to work.
    We disable NewCFGNode to prevent the addition of more nodes, but existing
    nodes also should not be changed.
    """
    assert self.entrypoint
    self._CompressGraph()
    self.solver = Solver(self)
    self.NewCFGNode = utils.disabled_function  # pylint: disable=invalid-name

  def MergeVariables(self, node, name, variables):
    """Create a combined Variable for a list of variables.

    The purpose of this function is to create a final result variable for
    functions that return a list of "temporary" variables. (E.g. function
    calls).

    Args:
      node: The current CFG node.
      name: Name of the new variable.
      variables: List of variables.
    Returns:
      A typegraph.Variable.
    """
    if not variables:
      return self.NewVariable(name)  # return empty var
    elif len(variables) == 1:
      v, = variables
      return v
    elif all(v is variables[0] for v in variables):
      return variables[0]
    else:
      v = self.NewVariable(name)
      for r in variables:
        v.PasteVariable(r, node)
      return v

  def _CompressGraph(self):
    """Compress the graph for faster traversal.

    This partitions the graph into lists of nodes called "supernodes," turning,
    for instance,
      n0 -> n1 -> n2 -> n3 -> n4
            |                  |
            -> n5 -> n6 -> n7 <-
    into
      [n0] -> [n1] -> [n2, n3, n4]-
               |                  |
               -> [n5, n6, n7] <---
    (It is also possible for n7 to be in the [n2, n3, n4] supernode.)  Every
    node stores a pointer to and its position in its supernode.
    """
    seen = set()
    stack = [self.entrypoint]
    while stack:
      node = stack.pop()
      if node in seen:
        continue
      seen.add(node)
      if len(node.incoming) == 1:
        node_in, = node.incoming
        if node_in.supernode and len(node_in.outgoing) == 1:
          node.supernode = node_in.supernode
          node.supernode.append(node)
          node.position = node_in.position + 1
      if not node.supernode:
        node.supernode = [node]
        node.position = 0
      stack.extend(node.outgoing)
    assert len(seen) == len(self.cfg_nodes)


class CFGNode(object):
  """A node in the CFG.

  Assignments within one CFG node are treated as unordered: E.g. if "x = x + 1"
  is in a single CFG node, both values for x will be visible from inside that
  node.

  Attributes:
    program: The Program instance we belong to
    id: Numerical node id.
    name: Name of this CFGNode, or None. For debugging.
    incoming: Other CFGNodes that are connected to this node.
    outgoing: CFGNodes we connect to.
    values: Values that are being assigned to Variables at this CFGNode.
    reachable_subset: A subset of the nodes reachable (going backwards) from
      this one.
    supernode: A list of nodes comprising a "supernode" to which this one
      belongs. See Program._CompressGraph.
    position: This node's position in the supernode.
  """
  __slots__ = ("program", "id", "name", "incoming", "outgoing", "values",
               "reachable_subset", "supernode", "position")

  def __init__(self, program, name, cfgnode_id):
    """Initialize a new CFG node. Called from Program.NewCFGNode."""
    self.program = program
    self.id = cfgnode_id
    self.name = name
    self.incoming = set()
    self.outgoing = set()
    self.values = set()  # filled through RegisterValue()
    self.reachable_subset = {self}
    self.supernode = None
    self.position = None

  def ConnectNew(self, name=None):
    """Add a new node connected to this node."""
    cfg_node = self.program.NewCFGNode(name)
    self.ConnectTo(cfg_node)
    return cfg_node

  def ConnectTo(self, cfg_node):
    """Connect this node to an existing node."""
    self.outgoing.add(cfg_node)
    cfg_node.incoming.add(self)
    cfg_node.reachable_subset |= self.reachable_subset

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
    # Optimization: check the entire combination only if all of the values are
    # possible separately.
    return (all(self.program.solver.Solve({value}, self) for value in values)
            and self.program.solver.Solve(values, self))

  def RegisterValue(self, value):
    self.values.add(value)

  def __repr__(self):
    return "<cfgnode %d %s>" % (self.id, self.name)


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
    return self.program.solver.Solve({self}, viewpoint)

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

  def HasSource(self, value):
    """Does this value depend on a given source?"""
    if self is value:
      return True
    for origin in self.origins:
      for source_set in origin.source_sets:
        for source in source_set:
          if source.HasSource(value):
            return True
    return False

  def __repr__(self):
    return "<value %x of variable %d>" % (id(self), self.variable.id)


class Variable(object):
  """A collection of possible values for a variable, along with their origins.

  A variable stores the values it can have as well as the CFG nodes at which
  the values occur. Callback functions can be registered with it, to be executed
  when a value is added. The values are stored in a list for determinicity; new
  values should be added via AddValue or (FilterAnd)PasteVariable rather than
  appended to values directly to ensure that values and _data_id_to_value are
  updated together. We do this rather than making _data_id_to_value a
  collections.OrderedDict because a CFG can easily have tens of thousands of
  variables, and it takes about 40x as long to create an OrderedDict instance as
  to create a list and a dict, while adding a value to the OrderedDict takes
  2-3x as long as adding it to both the list and the dict.
  """
  __slots__ = ("program", "name", "id", "values", "_data_id_to_value",
               "_cfgnode_to_values", "_callbacks")

  def __init__(self, program, name, variable_id):
    """Initialize a new Variable. Called through Program.NewVariable."""
    self.program = program
    self.name = name
    self.id = variable_id
    self.values = []
    self._data_id_to_value = {}
    self._cfgnode_to_values = collections.defaultdict(set)
    self._callbacks = []

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
    num_values = len(self.values)
    if (len(self._cfgnode_to_values) == 1 or num_values == 1) and any(
        node in viewpoint.reachable_subset for node in self._cfgnode_to_values):
      return self.values
    result = set()
    seen = set()
    stack = [viewpoint]
    while stack:
      if len(result) == num_values:
        break
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
      self.values.append(value)
      self._data_id_to_value[id(data)] = value
      for callback in self._callbacks:
        callback()
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
    assert not isinstance(data, Variable)
    value = self._FindOrAddValue(data)
    if source_set or where:
      assert source_set is not None and where is not None
      value.AddOrigin(where, source_set)
    return value

  def PasteVariable(self, variable, where):
    """Adds all the values from another variable to this one."""
    for value in variable.values:
      # TODO(kramm): If where == value.where, this should just copy the
      # source_sets from value, instead of adding another level of indirection
      # by creating a new source set with value in it.
      copy = self.AddValue(value.data)
      copy.AddOrigin(where, {value})

  def FilterAndPasteVariable(self, variable, where):
    """Adds all the visible values from another variable to this one."""
    for value in variable.Values(where):
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

  def RegisterChangeListener(self, callback):
    self._callbacks.append(callback)

  def UnregisterChangeListener(self, callback):
    self._callbacks.remove(callback)

  @property
  def data(self):
    return [value.data for value in self.values]

  @property
  def nodes(self):
    return set(self._cfgnode_to_values)


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
      True if we would need a variable to be assigned to two distinct
      values at the same time in order to solve this state. False if there are
      no conflicting goals.

    Raises:
      AssertionError: For internal errors.
    """
    variables = {}
    for goal in self.goals:
      existing = variables.get(goal.variable)
      if existing:
        if existing is goal:
          raise AssertionError("Internal error. Duplicate goal.")
        if existing.data is goal.data:
          raise AssertionError("Internal error. Duplicate data across values")
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
    return set.union(*(goal.variable.nodes for goal in self.goals))

  def Replace(self, goal, replace_with):
    """Replace a goal with new goals (the origins of the expanded goal)."""
    assert goal in self.goals, "goal to expand not in state"
    self.goals.remove(goal)
    self.goals.update(replace_with)

  def _AddSources(self, goal, seen_goals, new_goals):
    """If the goal is trivially fulfilled, add its sources as new goals.

    Args:
      goal: The goal.
      seen_goals: The set of previously seen goals, which will be augmented
        with goal. The caller is responsible for checking whether goal is
        already present.
      new_goals: The set of new goals, to which goal's sources are added iff
        this method returns True.

    Returns:
      True if the goal is trivially fulfilled and False otherwise.
    """
    seen_goals.add(goal)
    origin = goal.FindOrigin(self.pos)
    # For source sets > 2, we don't know which sources to use, so we have
    # to let the solver iterate over them later.
    if origin and len(origin.source_sets) <= 1:
      source_set, = origin.source_sets  # we always have at least one.
      new_goals.update(source_set)
      return True
    return False

  def RemoveFinishedGoals(self):
    """Remove all goals that are trivially fulfilled at the current CFG node."""
    seen_goals = set()
    new_goals = set()
    for goal in self.goals.copy():
      if self._AddSources(goal, seen_goals, new_goals):
        self.goals.remove(goal)
    # We might remove multiple layers of nested goals, so loop until we don't
    # find anything to replace anymore. Storing new goals in a separate set is
    # faster than adding and removing them from self.goals.
    while new_goals:
      goal = new_goals.pop()
      if goal in seen_goals:
        # Only process a given goal once, to prevent infinite loops for cyclic
        # data structures.
        continue
      if not self._AddSources(goal, seen_goals, new_goals):
        self.goals.add(goal)

  def __hash__(self):
    """Compute hash for this State. We use States as keys when memoizing."""
    return hash(self.pos) + hash(frozenset(self.goals))

  def __eq__(self, other):
    return self.pos == other.pos and self.goals == other.goals

  def __ne__(self, other):
    return not self == other


def _FindNodeBackwards(start, finish, blocked):
  """Determine whether we can reach a CFG node, going backwards.

  Traverse the CFG from a starting point to find a given node, but avoid any
  nodes marked as "blocked".

  Arguments:
    start: Start node.
    finish: Node we're looking for.
    blocked: A set of blocked nodes. We do not consider start or finish to be
      blocked even if they apppear in this set.

  Returns:
    True if we can find this node, False otherwise.
  """
  query = (start, finish, blocked)
  if query in _solved_find_queries:
    return _solved_find_queries[query]
  if start.supernode is finish.supernode and start.position >= finish.position:
    # There is exactly one path from start to finish. Check whether any node in
    # it is blocked.
    if blocked.intersection(start.supernode[finish.position+1:start.position]):
      found = False
    else:
      found = True
  elif blocked.intersection(
      start.supernode[:start.position] + finish.supernode[finish.position+1:]):
    # A node that must be passed through to get from start to finish is blocked.
    found = False
  else:
    found = _FindSupernodeBackwards(start.supernode[0], finish.supernode[0],
                                    frozenset(node.supernode[0]
                                              for node in blocked))
  _solved_find_queries[query] = found
  return found


def _FindSupernodeBackwards(start, finish, blocked_supernodes):
  """Determine whether we can reach a supernode, going backwards.

  Arguments:
    start: The first node in the supernode we're starting from.
    finish: The first node in the supernode we're looking for.
    blocked_supernodes: A set of the first node in every blocked supernode.

  Returns:
    True if we can find finish from any of start's *incoming nodes*, False
    otherwise. This means that if start and finish are in the same supernode,
    we must find a path from the supernode back to itself.
  """
  query = (start, blocked_supernodes)
  if query in _supernode_reachable:
    return finish in _supernode_reachable[query]
  stack = list(start.incoming)
  seen = set()
  while stack:
    node = stack.pop().supernode[0]
    if node is finish:
      return True
    if node in seen:
      continue
    seen.add(node)
    if node in blocked_supernodes:
      continue
    stack.extend(node.incoming)
  # If we haven't found finish, then the seen set contains all of the nodes
  # reachable from start.
  _supernode_reachable[query] = seen
  return False


class Solver(object):
  """The solver class is instantiated for a given "problem" instance.

  It maintains a cache of solutions for subproblems to be able to recall them if
  they reoccur in the solving process.
  """

  def __init__(self, program):
    """Initialize a solver instance. Every instance has their own cache.

    Arguments:
      program: The program we're in.
    """
    self.program = program
    self._solved_states = {}

  def Solve(self, start_attrs, start_node):
    """Try to solve the given problem.

    Try to prove one or more values starting (and going backwards from) a
    given node, all the way to the program entrypoint.

    Arguments:
      start_attrs: The assignments we're trying to have, at the start node.
      start_node: The CFG node where we want the assignments to be active.

    Returns:
      True if there is a path through the program that would give "start_attr"
      its value at the "start_node" program position. For larger programs, this
      might only look for a partial path (i.e., a path that doesn't go back all
      the way to the entry point of the program).
    """
    state = State(start_node, start_attrs)
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
    blocked = frozenset(blocked)
    # Find the goal cfg node that was assigned last.  Due to the fact that we
    # treat CFGs as DAGs, there's typically one unique cfg node with this
    # property.
    for goal in state.goals:
      # "goal" is the assignment we're trying to find.
      for origin in goal.origins:
        if _FindNodeBackwards(state.pos, origin.where, blocked):
          # This loop over multiple different combinations of origins is why
          # we need memoization of states.
          for source_set in origin.source_sets:
            new_state = State(origin.where, state.goals)
            new_state.Replace(goal, source_set)
            # Also remove all goals that are trivially fulfilled at the
            # new CFG node.
            new_state.RemoveFinishedGoals()
            if self._RecallOrFindSolution(new_state):
              return True
    return False
