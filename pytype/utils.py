"""Generic functions."""

import collections
import contextlib
import errno
import itertools
import os
import re
import shutil
import tempfile
import textwrap
import threading
import types


from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


def replace_extension(filename, new_extension):
  name, _ = os.path.splitext(filename)
  if new_extension.startswith("."):
    return name + new_extension
  else:
    return name + "." + new_extension


def variable_product(variables):
  """Take the Cartesian product of a number of Variables.

  Args:
    variables: A sequence of Variables.

  Returns:
    A list of lists of Values, where each sublist has one element from each
    of the given Variables.
  """
  return itertools.product(*(v.bindings for v in variables))


def _variable_product_items(variableitems):
  """Take the Cartesian product of a list of (key, value) tuples.

  See variable_product_dict below.

  Args:
    variableitems: A dict mapping object to typegraph.Variable.

  Yields:
    A sequence of [(key, typegraph.Value), ...] lists.
  """
  if variableitems:
    headkey, headvar = variableitems[0]
    for tail in _variable_product_items(variableitems[1:]):
      for headvalue in headvar.bindings:
        yield [(headkey, headvalue)] + tail
  else:
    yield []


def deep_variable_product(variables):
  """Take the deep Cartesian product of a list of Variables.

  For example:
    x1.children = {v2, v3}
    v1 = {x1, x2}
    v2 = {x3}
    v3 = {x4, x5}
    v4 = {x6}
  then
    deep_variable_product([v1, v4]) will return:
      [[x1, x3, x4, x6],
       [x1, x3, x5, x6],
       [x2, x6]]
  .
  Args:
    variables: A sequence of Variables.

  Returns:
    A list of lists of Values, where each sublist has one Value from each
    of the corresponding Variables and the Variables of their Values' children.
  """
  return _deep_values_list_product(v.bindings for v in variables)


def _deep_values_list_product(values_list, seen=()):
  """Take the deep Cartesian product of a list of list of Values."""
  result = []
  for row in itertools.product(*(values for values in values_list if values)):
    extra_params = sum([entry.data.unique_parameter_values()
                        for entry in row if entry not in seen], [])
    extra_values = (extra_params and
                    _deep_values_list_product(extra_params, seen + row))
    if extra_values:
      for new_row in extra_values:
        result.append(row + new_row)
    else:
      result.append(row)
  return result


def variable_product_dict(variabledict):
  """Take the Cartesian product of variables in the values of a dict.

  This Cartesian product is taken using the dict keys as the indices into the
  input and output dicts. So:
    variable_product_dict({"x": Variable(a, b), "y": Variable(c, d)})
      ==
    [{"x": a, "y": c}, {"x": a, "y": d}, {"x": b, "y": c}, {"x": b, "y": d}]
  This is exactly analogous to a traditional Cartesian product except that
  instead of trying each possible value of a numbered position, we are trying
  each possible value of a named position.

  Args:
    variabledict: A dict with variable values.

  Returns:
    A list of dicts with Value values.
  """
  return [dict(d) for d in _variable_product_items(variabledict.items())]


def maybe_truncate(s, length=30):
  """Truncate long strings (and append '...'), but leave short strings alone."""
  s = str(s)
  if len(s) > length-3:
    return s[0:length-3] + "..."
  else:
    return s


def pretty_conjunction(conjunction):
  """Pretty-print a conjunction. Use parentheses as necessary.

  E.g. ["a", "b"] -> "(a & b)"

  Args:
    conjunction: List of strings.
  Returns:
    A pretty-printed string.
  """
  if not conjunction:
    return "true"
  elif len(conjunction) == 1:
    return conjunction[0]
  else:
    return "(" + " & ".join(conjunction) + ")"


def pretty_dnf(dnf):
  """Pretty-print a disjunctive normal form (disjunction of conjunctions).

  E.g. [["a", "b"], ["c"]] -> "(a & b) | c".

  Args:
    dnf: A list of list of strings. (Disjunction of conjunctions of strings)
  Returns:
    A pretty-printed string.
  """
  if not dnf:
    return "false"
  else:
    return " | ".join(pretty_conjunction(c) for c in dnf)


def numeric_sort_key(s):
  return tuple((int(e) if e.isdigit() else e) for e in re.split(r"(\d+)", s))


def compute_predecessors(nodes):
  """Build a transitive closure.

  For a list of nodes, compute all the predecessors of each node.

  Args:
    nodes: A list of nodes or blocks.
  Returns:
    A dictionary that maps each node to a set of all the nodes that can reach
    that node.
  """
  # Our CFGs are reflexive: Every node can reach itself.
  predecessors = {n: {n} for n in nodes}

  # Start at the root and follow outgoing edges to update predecessors as
  # needed. Since the maximum number of times a given edge is processed is |V|,
  # the worst-case runtime is |V|*|E|. However, these graphs are typically
  # trees, so the usual runtime is much closer to |E|. Compared to using
  # Floyd-Warshall (|V|^3), this brings down the execution time on
  # pyglib/flags/flags_strict_test.py and pyglib/flags/flags_test.py
  # from about 30s to less than 7s.
  unprocessed = [(nodes[0], n) for n in nodes[0].outgoing]
  while unprocessed:
    from_node, node = unprocessed.pop(0)
    node_predecessors = predecessors[node]
    length_before = len(node_predecessors)
    # Add the predecessors of from_node to this node's predecessors
    node_predecessors |= predecessors[from_node]
    if length_before != len(node_predecessors):
      # All of the nodes directly reachable from this one need their
      # predecessors updated
      unprocessed.extend((node, n) for n in node.outgoing)

  return predecessors


def order_nodes(nodes):
  """Build an ancestors first traversal of CFG nodes.

  This guarantees that at least one predecessor of a block is scheduled before
  the block itself, and it also tries to schedule as many of them before the
  block as possible (so e.g. if two branches merge in a node, it prefers to
  process both the branches before that node).

  Args:
    nodes: A list of nodes or blocks. They have two attributes: "incoming" and
      "outgoing". Both are lists of other nodes.
  Returns:
    A list of nodes in the proper order.
  """
  if not nodes:
    return []
  root = nodes[0]
  predecessor_map = compute_predecessors(nodes)
  dead = {node for node, predecessors in predecessor_map.items()
          if root not in predecessors}
  queue = {root: predecessor_map[root]}
  order = []
  seen = set()
  while queue:
    # Find node with minimum amount of predecessors that's connected to a node
    # we already processed.
    _, _, node = min((len(predecessors), node.id, node)
                     for node, predecessors in queue.items())
    del queue[node]
    if node in seen:
      continue
    order.append(node)
    seen.add(node)
    # Remove this node from the predecessors of all nodes after it.
    for _, predecessors in queue.items():
      predecessors.discard(node)
    # Potentially schedule nodes we couldn't reach before:
    for n in node.outgoing:
      if n not in queue:
        queue[n] = predecessor_map[n] - seen

  # check that we don't have duplicates and that we didn't miss anything:
  assert len(set(order) | dead) == len(set(nodes))

  return order


def topological_sort(nodes):
  """Sort a list of nodes topologically.

  This will order the nodes so that any node that appears in the "incoming"
  list of another node n2 will appear in the output before n2. It assumes that
  the graph doesn't have any cycles.
  If there are multiple ways to sort the list, a random one is picked.

  Args:
    nodes: A sequence of nodes. Each node may have an attribute "incoming",
      a list of nodes (every node in this list needs to be in "nodes"). If
      "incoming" is not there, it's assumed to be empty. The list of nodes
      can't have duplicates.
  Yields:
    The nodes in their topological order.
  Raises:
    ValueError: If the graph contains a cycle.
  """
  incoming = {node: set(getattr(node, "incoming", ())) for node in nodes}
  outgoing = collections.defaultdict(set)
  for node in nodes:
    for inc in incoming[node]:
      outgoing[inc].add(node)
  stack = [node for node in nodes if not incoming[node]]
  for _ in nodes:
    if not stack:
      raise ValueError("Circular graph")
    leaf = stack.pop()
    yield leaf
    for out in outgoing[leaf]:
      incoming[out].remove(leaf)
      if not incoming[out]:
        stack.append(out)
  assert not stack


def flattened_superclasses(cls):
  """Given a pytd.Class return a list of all superclasses.

  Args:
    cls: A pytd.Class object.
  Returns:
    A frozenset of all superclasses of the given class including itself and any
    transitive superclasses.
  """
  if isinstance(cls, pytd.ClassType):
    cls = cls.cls
  return frozenset([cls]) | frozenset(c
                                      for base in cls.parents
                                      for c in flattened_superclasses(base))


class HashableDict(dict):
  """A dict subclass that can be hashed.

  Instances should not be modified. Methods that would modify the dictionary
  have been overwritten to throw an exception.
  """

  def __init__(self, *args, **kwargs):
    super(HashableDict, self).__init__(*args, **kwargs)
    self._hash = hash(frozenset(self.items()))

  def update(self):
    raise TypeError()

  def clear(self):
    raise TypeError()

  def pop(self):
    raise TypeError()

  def popitem(self):
    raise TypeError()

  def setdefault(self):
    raise TypeError()

  def __setitem__(self):
    raise TypeError()

  def __delitem__(self):
    raise TypeError()

  def __hash__(self):
    return self._hash


def compute_mro(c):
  """Compute the class precedence list (mro) according to C3.

  This code is copied from the following URL with print statements removed.
  https://www.python.org/download/releases/2.3/mro/

  Args:
    c: The Class to compute the MRO for. This needs to be an instance
      with the members "mro" and "bases".
  Returns:
    A list of Class objects in Method Resolution Order.
  """
  return tuple(pytd_utils.MROMerge([[c]] +
                                   [list(base.mro) for base in c.bases()] +
                                   [list(c.bases())]))


def concat_lists(lists):
  return list(itertools.chain.from_iterable(lists))


def concat_tuples(tuples):
  return tuple(itertools.chain.from_iterable(tuples))


def _makedirs(path):
  """Create a nested directory, but don't fail if any of it already exists."""
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise


class Tempdir(object):
  """Context handler for creating temporary directories."""

  def __enter__(self):
    self.path = tempfile.mkdtemp()
    return self

  def create_directory(self, filename):
    """Create a subdirectory in the temporary directory."""
    path = os.path.join(self.path, filename)
    _makedirs(path)
    return path

  def create_file(self, filename, indented_data=None):
    """Create a file in the temporary directory. Also dedents the contents."""
    filedir, filename = os.path.split(filename)
    if filedir:
      self.create_directory(filedir)
    path = os.path.join(self.path, filedir, filename)
    with open(path, "wb") as fi:
      if indented_data:
        fi.write(textwrap.dedent(indented_data))
    return path

  def __exit__(self, error_type, value, tb):
    shutil.rmtree(path=self.path)
    return False  # reraise any exceptions

  def __getitem__(self, filename):
    """Get the full path for an entry in this directory."""
    return os.path.join(self.path, filename)


def list_startswith(l, prefix):
  """Like str.startswith, but for lists."""
  return l[:len(prefix)] == prefix


def list_strip_prefix(l, prefix):
  """Remove prefix, if it's there."""
  return l[len(prefix):] if list_startswith(l, prefix) else l


def _arg_names(f):
  """Return the argument names of a function."""
  return f.func_code.co_varnames[:f.func_code.co_argcount]


class memoize(object):  # pylint: disable=invalid-name
  """A memoizing decorator that supports expressions as keys.

  Use it like this:
    @memoize
    def f(x):
      ...
  or
    @memoize("(id(x), y)")
    def f(x, y, z):
      ...
  .
  Careful with methods. If you have code like
    @memoize("x")
    def f(self, x):
      ...
  then memoized values will be shared across instances.

  This decorator contains some speed optimizations that make it not thread-safe.
  """

  def __new__(cls, key_or_function):
    if isinstance(key_or_function, types.FunctionType):
      f = key_or_function
      key = "(" + ", ".join(_arg_names(f)) + ")"
      return memoize(key)(f)
    else:
      key = key_or_function
      return object.__new__(cls, key)

  def __init__(self, key):
    self.key = key

  def __call__(self, f):
    key_program = compile(self.key, filename=__name__, mode="eval")
    argnames = _arg_names(f)
    memoized = {}
    no_result = object()
    if f.func_defaults:
      defaults = dict(zip(argnames[-len(f.func_defaults):], f.func_defaults))
    else:
      defaults = {}
    pos_and_arg_tuples = zip(range(f.func_code.co_argcount), argnames)
    shared_dict = {}
    # TODO(kramm): Use functools.wraps or functools.update_wrapper to preserve
    # the metadata of the original function.
    def call(*posargs, **kwargs):
      """Call a memoized function."""
      if kwargs or defaults:
        # Slower version; for default arguments, we need two dictionaries.
        args = defaults.copy()
        args.update(dict(zip(argnames, posargs)))
        args.update(kwargs)
        key = eval(key_program, args)  # pylint: disable=eval-used
      else:
        # Faster version, if we have no default args.
        for pos, arg in pos_and_arg_tuples:
          # We know we write *all* the values, so we can re-use the dictionary.
          shared_dict[arg] = posargs[pos]
        key = eval(key_program, shared_dict)  # pylint: disable=eval-used
      result = memoized.get(key, no_result)
      if result is no_result:
        # Call the actual function.
        result = f(*posargs, **kwargs)
        memoized[key] = result
      return result
    return call


class MonitorDict(dict):
  """A dictionary that monitors changes to its cfg.Variable values.

  This dictionary takes arbitrary objects as keys and cfg.Variable objects as
  values. It increments a changestamp whenever a new value is added or more data
  is merged into a value. The changestamp is unaffected by the addition of
  another origin for existing data.
  """

  def __init__(self, *args, **kwargs):
    super(MonitorDict, self).__init__(*args, **kwargs)
    self.changestamp = 0
    for var in self.values():
      var.RegisterChangeListener(self._changed)

  def __delitem__(self, name):
    self[name].UnregisterChangeListener(self._changed)
    super(MonitorDict, self).__delitem__(name)
    self._changed()

  def __setitem__(self, name, var):
    if name in self:
      self[name].UnregisterChangeListener(self._changed)
    super(MonitorDict, self).__setitem__(name, var)
    var.RegisterChangeListener(self._changed)
    self._changed()

  def _changed(self):
    self.changestamp += 1

  @property
  def data(self):
    return itertools.chain.from_iterable(v.data for v in self.values())


class DynamicVar(object):
  """A dynamically scoped variable.

  This is a per-thread dynamic variable, with an initial value of None.
  The bind() call establishes a new value that will be in effect for the
  duration of the resulting context manager.  This is intended to be used
  in conjunction with a decorator.
  """

  def __init__(self):
    self._local = threading.local()

  def _values(self):
    values = getattr(self._local, "values", None)
    if values is None:
      values = [None]  # Stack of bindings, with an initial default of None.
      self._local.values = values
    return values

  @contextlib.contextmanager
  def bind(self, value):
    """Bind the dynamic variable to the supplied value."""
    values = self._values()
    try:
      values.append(value)  # Push the new binding.
      yield
    finally:
      values.pop()  # Pop the binding.

  def get(self):
    """Return the current value of the dynamic variable."""
    return self._values()[-1]


class AnnotatingDecorator(object):
  """A decorator for storing function attributes.

  Attributes:
    mapping: maps functions to their attributes.
  """

  def __init__(self):
    self.lookup = {}

  def __call__(self, value):
    def decorate(f):
      self.lookup[f.__name__] = value
      return f
    return decorate

