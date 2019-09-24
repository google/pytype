"""Points-to / dataflow / cfg graph engine.

It can be used to run reaching-definition queries on a nested CFG graph
and to model path-specific visibility of nested data structures.
"""

import collections
import logging

from pytype import metrics

log = logging.getLogger(__name__)


_variable_size_metric = metrics.Distribution("variable_size")


# Across a sample of 19352 modules, for files which took more than 25 seconds,
# the largest variable was, on average, 157. For files below 25 seconds, it was
# 7. Additionally, for 99% of files, the largest variable was below 64, so we
# use that as the cutoff.
MAX_VAR_SIZE = 64


class Program(object):
  """Program instances describe program entities.

  This class ties together the CFG, the data flow graph (variables + bindings)
  as well as methods. We use this for issuing IDs: We need every CFG node to
  have a unique ID, and this class does the corresponding counting.

  Attributes:
    entrypoint: Entrypoint of the program, if it has one. (None otherwise)
    cfg_nodes: CFG nodes in use. Will be used for assigning node IDs.
    next_variable_id: The next id to assign to a variable.
    solver: the active Solver instance.
    default_data: Default value for data.
    variables: Variables in use. Will be used for assigning variable IDs.
  """

  def __init__(self):
    """Initialize a new (initially empty) program."""
    self.entrypoint = None
    self.cfg_nodes = []
    self.next_variable_id = 0
    self.solver = None
    self.default_data = None

  def CreateSolver(self):
    if self.solver is None:
      self.solver = Solver(self)
    return self.solver

  def InvalidateSolver(self):
    self.solver = None

  def NewCFGNode(self, name=None, condition=None):
    """Start a new CFG node."""
    self.InvalidateSolver()
    cfg_node = CFGNode(self, name, len(self.cfg_nodes), condition)
    self.cfg_nodes.append(cfg_node)
    return cfg_node

  @property
  def variables(self):
    ret = set()
    for node in self.cfg_nodes:
      ret.update(b.variable for b in node.bindings)
    return ret

  def NewVariable(self, bindings=None, source_set=None, where=None):
    """Create a new Variable.

    A Variable typically models a "union type", i.e., a disjunction of different
    possible types.  This constructor assumes that all the bindings in this
    Variable have the same origin(s). If that's not the case, construct a
    variable with bindings=[] and origins=[] and then call AddBinding() to add
    the different bindings.

    Arguments:
      bindings: Optionally, a sequence of possible data items this variable can
        have.
      source_set: If we have bindings, the source_set they *all* depend on. An
        instance of SourceSet.
      where: If we have bindings, where in the CFG they're assigned.

    Returns:
      A Variable instance.
    """
    variable = Variable(self, self.next_variable_id)
    self.next_variable_id += 1
    if bindings is not None:
      assert source_set is not None and where is not None
      for data in bindings:
        binding = variable.AddBinding(data)
        binding.AddOrigin(where, source_set)
    return variable

  def is_reachable(self, src, dst):  # pylint: disable=invalid-name
    """Whether a path exists (going forward) from node src to node dst."""
    return _PathFinder().FindAnyPathToNode(dst, src, frozenset())


class CFGNode(object):
  """A node in the CFG.

  Assignments within one CFG node are treated as unordered: E.g. if "x = x + 1"
  is in a single CFG node, both bindings for x will be visible from inside that
  node.

  Attributes:
    program: The Program instance we belong to
    id: Numerical node id.
    name: Name of this CFGNode, or None. For debugging.
    incoming: Other CFGNodes that are connected to this node.
    outgoing: CFGNodes we connect to.
    bindings: Bindings that are being assigned to Variables at this CFGNode.
    condition: None if no condition is set at this node;
               The binding representing the condition which needs to be
                 fulfilled to take the branch represented by this node.
  """
  __slots__ = ("program", "id", "name", "incoming", "outgoing", "bindings",
               "condition")

  def __init__(self, program, name, cfgnode_id, condition):
    """Initialize a new CFG node. Called from Program.NewCFGNode."""
    self.program = program
    self.id = cfgnode_id
    self.name = name
    self.incoming = set()
    self.outgoing = set()
    self.bindings = set()  # filled through RegisterBinding()
    self.condition = condition

  def ConnectNew(self, name=None, condition=None):
    """Add a new node connected to this node."""
    cfg_node = self.program.NewCFGNode(name, condition)
    self.ConnectTo(cfg_node)
    return cfg_node

  def ConnectTo(self, cfg_node):
    """Connect this node to an existing node."""
    self.program.InvalidateSolver()
    self.outgoing.add(cfg_node)
    cfg_node.incoming.add(self)

  def CanHaveCombination(self, bindings):
    """Quick version of HasCombination below."""
    goals = set(bindings)
    seen = set()
    stack = [self]
    while stack and goals:
      node = stack.pop()
      if node in seen:
        continue
      seen.add(node)
      goals -= node.bindings
      stack.extend(node.incoming)
    return not goals

  def HasCombination(self, bindings):
    """Query whether a combination is possible.

    Query whether its possible to have the given combination of bindings at
    this CFG node (I.e., whether they can all be assigned at the same time.)
    This will e.g. tell us whether a return binding is possible given a specific
    combination of argument bindings.

    Arguments:
      bindings: A list of Bindings.
    Returns:
      True if the combination is possible, False otherwise.
    """
    self.program.CreateSolver()
    # Optimization: check the entire combination only if all of the bindings
    # are possible separately.
    return (all(self.program.solver.Solve({b}, self) for b in bindings)
            and self.program.solver.Solve(bindings, self))

  def RegisterBinding(self, binding):
    self.bindings.add(binding)

  def __repr__(self):
    if self.condition:
      return "<cfgnode %d %s condition:%s>" % (self.id, self.name,
                                               self.condition.variable.id)
    else:
      return "<cfgnode %d %s>" % (self.id, self.name)


class SourceSet(frozenset):
  """A SourceSet is a combination of Bindings that was used to form a Binding.

  In this context, a "source" is a Binding that was used to create another
  Binding.  E.g., for a statement like "z = a.x + y", a, a.x and y would be the
  Sources to create z, and would form a SourceSet.
  """
  __slots__ = ()


class Origin(collections.namedtuple("_", "where, source_sets")):
  """An "origin" is an explanation of how a binding was constructed.

  It consists of a CFG node and a set of sourcesets.

  Attributes:
    where: The CFG node where this assignment happened.
    source_sets: Possible SourceSets used to construct the binding we belong to.
      A set of SourceSet instances.
  """
  __slots__ = ()

  def __new__(cls, where, source_sets=None):
    return super(Origin, cls).__new__(
        cls, where, source_sets or set())

  def AddSourceSet(self, source_set):
    """Add a new possible source set."""
    self.source_sets.add(SourceSet(source_set))


class Binding(object):
  """A Binding assigns a binding to a (specific) variable.

  Bindings will therefore be stored in a dictionary in the Variable class,
  mapping strings to Binding instances.
  Depending on context, a Binding might also be called a "Source" (if it's
  used for creating another binding) or a "goal" (if we want to find a solution
  for a path through the program that assigns it).

  A binding has history ("origins"): It knows where the binding was
  originally retrieved from, before being assigned to something else here.
  Origins contain, through source_sets, "sources", which are other bindings.
  """
  __slots__ = ("program", "variable", "origins", "data", "_cfgnode_to_origin")

  def __init__(self, program, variable, data):
    """Initialize a new Binding. Usually called through Variable.AddBinding."""
    self.program = program
    self.variable = variable
    self.origins = []
    self.data = data
    self._cfgnode_to_origin = {}

  def IsVisible(self, viewpoint):
    """Can we "see" this binding from the current cfg node?

    This will run a solver to determine whether there's a path through the
    program that makes our variable have this binding at the given CFG node.

    Arguments:
      viewpoint: The CFG node at which this binding is possible / not possible.

    Returns:
      True if there is at least one path through the program
      in which the binding was assigned (and not overwritten afterwards), and
      all the bindings it depends on were assigned (and not overwritten) before
      that, etc.
    """
    self.program.CreateSolver()
    return self.program.solver.Solve({self}, viewpoint)

  def _FindOrAddOrigin(self, cfg_node):
    try:
      origin = self._cfgnode_to_origin[cfg_node]
    except KeyError:
      origin = Origin(cfg_node)
      self.origins.append(origin)
      self._cfgnode_to_origin[cfg_node] = origin
      self.variable.RegisterBindingAtNode(self, cfg_node)
      cfg_node.RegisterBinding(self)
    return origin

  def FindOrigin(self, cfg_node):
    """Return an Origin instance for a CFGNode, or None."""
    return self._cfgnode_to_origin.get(cfg_node)

  def AddOrigin(self, where, source_set):
    """Add another possible origin to this binding."""
    self.program.InvalidateSolver()
    origin = self._FindOrAddOrigin(where)
    origin.AddSourceSet(source_set)

  def CopyOrigins(self, other_binding, where, additional_sources=None):
    """Copy the origins from another binding."""
    additional_sources = additional_sources or frozenset()
    if not where:
      for origin in other_binding.origins:
        for source_set in origin.source_sets:
          self.AddOrigin(origin.where, source_set | additional_sources)
    else:
      self.AddOrigin(where, {other_binding} | additional_sources)

  def AssignToNewVariable(self, where=None):
    """Assign this binding to a new variable."""
    variable = self.program.NewVariable()
    new_binding = variable.AddBinding(self.data)
    new_binding.CopyOrigins(self, where)
    return variable

  def HasSource(self, binding):
    """Does this binding depend on a given source?"""
    if self is binding:
      return True
    for origin in self.origins:
      for source_set in origin.source_sets:
        for source in source_set:
          if source.HasSource(binding):
            return True
    return False

  def __repr__(self):
    data_id = getattr(self.data, "id", id(self.data))
    return "<binding of variable %d to data %d>" % (self.variable.id, data_id)


class Variable(object):
  """A collection of possible bindings for a variable, along with their origins.

  A variable stores the bindings it can have as well as the CFG nodes at which
  the bindings occur. The bindings are stored in a list for determinicity; new
  bindings should be added via AddBinding or (FilterAnd)PasteVariable rather
  than appended to bindings directly to ensure that bindings and
  _data_id_to_bindings are updated together. We do this rather than making
  _data_id_to_binding a collections.OrderedDict because a CFG can easily have
  tens of thousands of variables, and it takes about 40x as long to create an
  OrderedDict instance as to create a list and a dict, while adding a binding to
  the OrderedDict takes 2-3x as long as adding it to both the list and the dict.
  """
  __slots__ = ("program", "id", "bindings", "_data_id_to_binding",
               "_cfgnode_to_bindings")

  def __init__(self, program, variable_id):
    """Initialize a new Variable. Called through Program.NewVariable."""
    self.program = program
    self.id = variable_id
    self.bindings = []
    self._data_id_to_binding = {}
    self._cfgnode_to_bindings = {}

  def __repr__(self):
    return "<Variable v%d: %d choices>" % (
        self.id, len(self.bindings))

  __str__ = __repr__

  def Bindings(self, viewpoint, strict=True):
    """Filters down the possibilities of bindings for this variable.

    It determines this by analyzing the control flow graph. Any definition for
    this variable that is invisible from the current point in the CFG is
    filtered out. This function differs from Filter() in that it only honors the
    CFG, not the source sets. As such, it's much faster.

    Arguments:
      viewpoint: The CFG node at which to determine the possible bindings.
      strict: Whether to allow approximations for speed.

    Returns:
      A filtered list of bindings for this variable.
    """
    if viewpoint is None or (not strict and len(self.bindings) == 1):
      return self.bindings

    num_bindings = len(self.bindings)
    result = set()
    seen = set()
    stack = [viewpoint]
    while stack:
      if len(result) == num_bindings:
        break
      node = stack.pop()
      seen.add(node)
      bindings = self._cfgnode_to_bindings.get(node)
      if bindings is not None:
        assert bindings, "empty binding list"
        result.update(bindings)
        # Don't expand this node - previous assignments to this variable will
        # be invisible, since they're overwritten here.
        continue
      else:
        stack.extend(set(node.incoming) - seen)
    return result

  def Data(self, viewpoint):
    """Like Bindings(cfg_node), but only return the data."""
    return [binding.data for binding in self.Bindings(viewpoint)]

  def Filter(self, viewpoint, strict=True):
    """Filters down the possibilities of this variable.

    It analyzes the control flow graph. Any definition for this variable that is
    impossible at the current point in the CFG is filtered out.

    Arguments:
      viewpoint: The CFG node at which to determine the possible bindings.
      strict: Whether to allow approximations for speed.

    Returns:
      A filtered list of bindings for this variable.
    """
    if not strict and len(self.bindings) == 1:
      return self.bindings
    else:
      return [b for b in self.bindings if b.IsVisible(viewpoint)]

  def FilteredData(self, viewpoint, strict=True):
    """Like Filter(viewpoint), but only return the data."""
    if not strict and len(self.bindings) == 1:
      return self.data
    else:
      return [b.data for b in self.bindings if b.IsVisible(viewpoint)]

  def _FindOrAddBinding(self, data):
    """Add a new binding if necessary, otherwise return existing binding."""
    if (len(self.bindings) >= MAX_VAR_SIZE - 1 and
        id(data) not in self._data_id_to_binding):
      data = self.program.default_data
    try:
      binding = self._data_id_to_binding[id(data)]
    except KeyError:
      self.program.InvalidateSolver()
      binding = Binding(self.program, self, data)
      self.bindings.append(binding)
      self._data_id_to_binding[id(data)] = binding
      _variable_size_metric.add(len(self.bindings))
    return binding

  def AddBinding(self, data, source_set=None, where=None):
    """Add another choice to this variable.

    This will not overwrite this variable in the current CFG node.  (It's
    legitimate to have multiple bindings for a variable on the same CFG node,
    e.g. if a union type is introduced at that node.)

    Arguments:
      data: A user specified object to uniquely identify this binding.
      source_set: An instance of SourceSet, i.e. a set of instances of Origin.
      where: Where in the CFG this variable was assigned to this binding.

    Returns:
      The new binding.
    """
    assert not isinstance(data, Variable)
    binding = self._FindOrAddBinding(data)
    if source_set or where:
      assert source_set is not None and where is not None
      binding.AddOrigin(where, source_set)
    return binding

  def PasteVariable(self, variable, where=None, additional_sources=None):
    """Adds all the bindings from another variable to this one."""
    for binding in variable.bindings:
      self.PasteBinding(binding, where, additional_sources)

  def PasteBinding(self, binding, where=None, additional_sources=None):
    """Adds a binding from another variable to this one."""
    new_binding = self.AddBinding(binding.data)
    if all(origin.where is where for origin in binding.origins):
      # Optimization: If all the bindings of the old variable happen at the
      # same CFG node as the one we're assigning now, we can copy the old
      # source_set instead of linking to it. That way, the solver has to
      # consider fewer levels.
      new_binding.CopyOrigins(binding, None, additional_sources)
    else:
      new_binding.CopyOrigins(binding, where, additional_sources)

  def AssignToNewVariable(self, where=None):
    """Assign this variable to a new variable.

    This is essentially a copy: All entries in the Union will be copied to
    the new variable, but with the corresponding current variable binding
    as an origin.

    Arguments:
      where: CFG node where the assignment happens.

    Returns:
      A new variable.
    """
    new_variable = self.program.NewVariable()
    for binding in self.bindings:
      new_binding = new_variable.AddBinding(binding.data)
      new_binding.CopyOrigins(binding, where)
    return new_variable

  def RegisterBindingAtNode(self, binding, node):
    if node not in self._cfgnode_to_bindings:
      self._cfgnode_to_bindings[node] = {binding}
    else:
      self._cfgnode_to_bindings[node].add(binding)

  @property
  def data(self):
    return [binding.data for binding in self.bindings]

  @property
  def nodes(self):
    return set(self._cfgnode_to_bindings)


def _GoalsConflict(goals):
  """Are the given bindings conflicting?

  Args:
    goals: A list of goals.

  Returns:
    True if we would need a variable to be assigned to two distinct
    bindings at the same time in order to solve this combination of goals.
    False if there are no conflicting goals.

  Raises:
    AssertionError: For internal errors.
  """
  variables = {}
  for goal in goals:
    existing = variables.get(goal.variable)
    if existing:
      if existing is goal:
        raise AssertionError("Internal error. Duplicate goal.")
      if existing.data is goal.data:
        raise AssertionError("Internal error. Duplicate data across bindings")
      return True
    variables[goal.variable] = goal
  return False


class State(object):
  """A state needs to "solve" a list of goals to succeed.

  Attributes:
    pos: Our current position in the CFG.
    goals: A list of bindings we'd like to be valid at this position.
  """
  __slots__ = ("pos", "goals")

  def __init__(self, pos, goals):
    """Initialize a state that starts at the given cfg node."""
    assert all(isinstance(goal, Binding) for goal in goals)
    self.pos = pos
    self.goals = set(goals)  # Make a copy. We modify these.

  def RemoveFinishedGoals(self):
    """Remove all goals that can be fulfilled at the current CFG node.

    Generates all possible sets of new goals obtained by replacing a goal that
    originates at the current node with one of its source sets, iteratively,
    until there are no more such goals. Generating these possibilities here
    allows every _FindSolution() call to completely process its input state,
    avoiding bugs related to transmitting state information across calls.

    Yields:
      (removed_goals, new_goals) tuples.
    """
    goals_to_remove = self.pos.bindings & self.goals
    seen_goals = set()
    removed_goals = set()
    new_goals = self.goals - goals_to_remove
    stack = [(goals_to_remove, seen_goals, removed_goals, new_goals)]
    # We might remove multiple layers of nested goals, so loop until we don't
    # find anything to replace anymore.
    while stack:
      goals_to_remove, seen_goals, removed_goals, new_goals = stack.pop(0)
      if goals_to_remove:
        goal = goals_to_remove.pop()
        if goal in seen_goals:
          # Only process a given goal once, to prevent infinite loops for
          # cyclic data structures.
          stack.append((goals_to_remove, seen_goals, removed_goals, new_goals))
          continue
        seen_goals.add(goal)
        origin = goal.FindOrigin(self.pos)
        if origin is None:
          new_goals.add(goal)
          stack.append((goals_to_remove, seen_goals, removed_goals, new_goals))
        else:
          removed_goals.add(goal)
          for source_set in origin.source_sets:
            stack.append((goals_to_remove | source_set, set(seen_goals),
                          set(removed_goals), set(new_goals)))
      else:
        yield removed_goals, new_goals

  def __hash__(self):
    """Compute hash for this State. We use States as keys when memoizing."""
    return hash(self.pos) + hash(frozenset(self.goals))

  def __eq__(self, other):
    return self.pos == other.pos and self.goals == other.goals

  def __ne__(self, other):
    return not self == other


class _PathFinder(object):
  """Finds a path between two nodes and collects nodes with conditions."""

  def __init__(self):
    self._solved_find_queries = {}

  def FindAnyPathToNode(self, start, finish, blocked):
    """Determine whether we can reach a node at all.

    Args:
      start: The node to start at. If this node appears in blocked, we can't
        reach finish (unless start==finish).
      finish: The node we're trying to reach. This node is always considered
        traversable, even if it appears in blocked.
      blocked: A set of nodes we're not allowed to traverse.

    Returns:
      True if we can reach finish from start, False otherwise.
    """
    stack = [start]
    seen = set()
    while stack:
      node = stack.pop()
      if node is finish:
        return True
      if node in seen or node in blocked:
        continue
      seen.add(node)
      stack.extend(node.incoming)
    return False

  def FindShortestPathToNode(self, start, finish, blocked):
    """Find a shortest path from start to finish, going backwards.

    Args:
      start: The node to start at. If this node appears in blocked, we can't
        reach finish (unless start==finish).
      finish: The node we're trying to reach. This node is always considered
        reachable, even if it appears in blocked.
      blocked: A set of nodes we're not allowed to traverse.

    Returns:
      An iterable over nodes, representing the shortest path (as
      [start, ..., finish]), or None if no path exists.
    """
    queue = collections.deque([start])
    previous = {start: None}
    seen = set()
    while queue:
      node = queue.popleft()
      if node is finish:
        break
      if node in seen or node in blocked:
        continue
      seen.add(node)
      for n in node.incoming:
        if n not in previous:
          previous[n] = node
      queue.extend(node.incoming)
    else:
      return None
    node = finish
    path = collections.deque()
    while node:
      path.appendleft(node)
      node = previous[node]
    return path

  def FindHighestReachableWeight(self, start, seen, weight_map):
    """Determine the highest weighted node we can reach, going backwards.

    Args:
      start: The node to start at. This node is always expanded, even if
        it appears in seen. The start node's weight is never considered, even
        if it's the only node with a weight.
      seen: Modified by this function. A set of nodes we're not allowed to
        traverse. This doesn't apply to the node with the highest weight, as
        long as we can reach it without traversing any other nodes in "seen".
      weight_map: A mapping from node to integer, specifying the weights, for
        nodes that have one.

    Returns:
      The node with the highest weight, or None if we didn't find any nodes
      with weights (or if the start node is the only node that has a weight).
    """
    stack = list(start.incoming)
    best_weight = -1
    best_node = None
    while stack:
      node = stack.pop()
      if node is start:
        continue  # don't allow loops back to start
      weight = weight_map.get(node, -1)
      if weight > best_weight:
        best_weight = weight
        best_node = node
      if node in seen:
        continue
      seen.add(node)
      stack.extend(node.incoming)
    return best_node

  def FindNodeBackwards(self, start, finish, blocked):
    """Determine whether we can reach a CFG node, going backwards.

    This also determines the "articulation points" of the graph, between the
    start and the finish node. In other words, it finds the nodes
    (only considering nodes with conditions) that are on *all* possible paths
    from start to finish.

    Arguments:
      start: The node to start at. If this node appears in blocked, we can't
        reach finish (unless start==finish).
      finish: The node we're trying to reach. This node is always considered
        traversable, even if it appears in blocked.
      blocked: A set of nodes we're not allowed to traverse.

    Returns:
      A tuple (Boolean, Iterable[CFGNode]). The boolean is true iff a path
      exists from start to finish. The Iterable contains all nodes with a
      condition, that are on *all* paths from start to finish, ordered by when
      they occur on said path(s).
    """
    query = (start, finish, blocked)
    if query in self._solved_find_queries:
      return self._solved_find_queries[query]
    shortest_path = self.FindShortestPathToNode(start, finish, blocked)
    if shortest_path is None:
      result = False, ()
    else:
      # We now have the shortest path to finish. All articulation points are
      # guaranteed to be on that path (since they're on *all* possible paths).
      # Now "block" the path we found, and check how far we can go
      # without using any nodes on it. The furthest node we can reach (described
      # below by the "weight", which is the position on our shortest path) is
      # our first articulation point. Set that as new start and continue.
      blocked = set(blocked)
      blocked.update(shortest_path)
      weights = {node: i for i, node in enumerate(shortest_path)}
      path = []
      node = start
      while True:
        if node.condition:
          path.append(node)
        if node is finish:
          break
        node = self.FindHighestReachableWeight(node, blocked, weights)
      result = True, path
    self._solved_find_queries[query] = result
    return result


class Solver(object):
  """The solver class is instantiated for a given "problem" instance.

  It maintains a cache of solutions for subproblems to be able to recall them if
  they reoccur in the solving process.
  """

  _cache_metric = metrics.MapCounter("cfg_solver_cache")
  _goals_per_find_metric = metrics.Distribution("cfg_solver_goals_per_find")

  def __init__(self, program):
    """Initialize a solver instance. Every instance has their own cache.

    Arguments:
      program: The program we're in.
    """
    self.program = program
    self._solved_states = {}
    self._path_finder = _PathFinder()

  def Solve(self, start_attrs, start_node):
    """Try to solve the given problem.

    Try to prove one or more bindings starting (and going backwards from) a
    given node, all the way to the program entrypoint.

    Arguments:
      start_attrs: The assignments we're trying to have, at the start node.
      start_node: The CFG node where we want the assignments to be active.

    Returns:
      True if there is a path through the program that would give "start_attr"
      its binding at the "start_node" program position. For larger programs,
      this might only look for a partial path (i.e., a path that doesn't go
      back all the way to the entry point of the program).
    """
    state = State(start_node, start_attrs)
    return self._RecallOrFindSolution(state)

  def _RecallOrFindSolution(self, state):
    """Memoized version of FindSolution()."""
    if state in self._solved_states:
      Solver._cache_metric.inc("hit")
      return self._solved_states[state]

    # To prevent infinite loops, we insert this state into the hashmap as a
    # solvable state, even though we have not solved it yet. The reasoning is
    # that if it's possible to solve this state at this level of the tree, it
    # can also be solved in any of the children.
    self._solved_states[state] = True

    Solver._cache_metric.inc("miss")
    result = self._solved_states[state] = self._FindSolution(state)
    return result

  def _FindSolution(self, state):
    """Find a sequence of assignments that would solve the given state."""
    if state.pos.condition:
      state.goals.add(state.pos.condition)
    Solver._goals_per_find_metric.add(len(state.goals))
    for removed_goals, new_goals in state.RemoveFinishedGoals():
      assert not state.pos.bindings & new_goals
      if _GoalsConflict(removed_goals):
        continue  # We bulk-removed goals that are internally conflicting.
      if not new_goals:
        return True
      blocked = frozenset().union(*(goal.variable.nodes for goal in new_goals))
      new_positions = set()
      for goal in new_goals:
        # "goal" is the assignment we're trying to find.
        for origin in goal.origins:
          path_exist, path = self._path_finder.FindNodeBackwards(
              state.pos, origin.where, blocked)
          if path_exist:
            where = origin.where
            # Check if we found conditions on the way.
            for node in path:
              if node is not state.pos:
                where = node
                break
            new_positions.add(where)
      for new_pos in new_positions:
        new_state = State(new_pos, new_goals)
        if self._RecallOrFindSolution(new_state):
          return True
    return False
