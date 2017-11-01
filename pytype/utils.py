"""Generic functions."""

import atexit
import collections
import contextlib
import errno
import itertools
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import types


# Limit on how many argument combinations we allow before aborting.
# For a sample of 16664 (sane) source files without imports, these are the
# quantiles that were below the given number of argument combinations:
#     50%  75%  90%  99%  99.9%  99.99%
#       1    3    6   57    809    9638
# We also know of two problematic files, with 4,800 and 10,000
# combinations, respectively.
# So pick a number that excludes as few files as possible (0.1%) but also
# cuts off problematic files, with a comfortable margin.
DEEP_VARIABLE_LIMIT = 1024


class UsageError(Exception):
  """Raise this for top-level usage errors."""
  pass


def format_version(python_version):
  """Format a version tuple into a dotted version string."""
  return ".".join([str(x) for x in python_version])


def parse_version(version_string):
  """Parse a version string like 2.7 into a tuple."""
  return tuple(map(int, version_string.split(".")))


def validate_version(python_version):
  """Raise an exception if the python version is unsupported."""
  if len(python_version) != 2:
    # This is typically validated in the option parser, but check here too in
    # case we get python_version via a different entry point.
    raise UsageError("python_version must be <major>.<minor>: %r" %
                     format_version(python_version))
  if (3, 0) <= python_version <= (3, 3):
    # These have odd __build_class__ parameters, store co_code.co_name fields
    # as unicode, and don't yet have the extra qualname parameter to
    # MAKE_FUNCTION. Jumping through these extra hoops is not worth it, given
    # that typing.py isn't introduced until 3.5, anyway.
    raise UsageError(
        "Python versions 3.0 - 3.3 are not supported. Use 3.4 and higher.")
  if python_version > (3, 6):
    # We have an explicit per-minor-version mapping in opcodes.py
    raise UsageError("Python versions > 3.6 are not yet supported.")


def is_python_2(python_version):
  return python_version[0] == 2


def is_python_3(python_version):
  return python_version[0] == 3


def get_builtins_path(python_version):
  if is_python_2(python_version):
    return "builtins/2"
  else:
    return "builtins/3"


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


def _variable_product_items(variableitems, complexity_limit):
  """Take the Cartesian product of a list of (key, value) tuples.

  See variable_product_dict below.

  Args:
    variableitems: A dict mapping object to cfg.Variable.
    complexity_limit: A counter that tracks how many combinations we've yielded
      and aborts if we go over the limit.

  Yields:
    A sequence of [(key, cfg.Binding), ...] lists.
  """
  if variableitems:
    headkey, headvar = variableitems[0]
    for tail in _variable_product_items(variableitems[1:], complexity_limit):
      for headvalue in headvar.bindings:
        complexity_limit.inc()
        yield [(headkey, headvalue)] + tail
  else:
    yield []


class TooComplexError(Exception):
  """Thrown if we determine that something in our program is too complex."""


class ComplexityLimit(object):
  """A class that raises TooComplexError if we hit a limit."""

  def __init__(self, limit):
    self.limit = limit
    self.count = 0

  def inc(self, add=1):
    self.count += add
    if self.count >= self.limit:
      raise TooComplexError()


def deep_variable_product(variables, limit=DEEP_VARIABLE_LIMIT):
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
    limit: How many results we allow before aborting.

  Returns:
    A list of lists of Values, where each sublist has one Value from each
    of the corresponding Variables and the Variables of their Values' children.

  Raises:
    TooComplexError: If we expanded too many values.
  """
  return _deep_values_list_product((v.bindings for v in variables), set(),
                                   ComplexityLimit(limit))


def _deep_values_list_product(values_list, seen, complexity_limit):
  """Take the deep Cartesian product of a list of list of Values."""
  result = []
  for row in itertools.product(*(values for values in values_list if values)):
    extra_params = sum([entry.data.unique_parameter_values()
                        for entry in row if entry not in seen], [])
    extra_values = (extra_params and
                    _deep_values_list_product(extra_params, seen.union(row),
                                              complexity_limit))
    if extra_values:
      for new_row in extra_values:
        result.append(row + new_row)
    else:
      complexity_limit.inc()
      result.append(row)
  return result


def variable_product_dict(variabledict, limit=DEEP_VARIABLE_LIMIT):
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
    limit: How many results to allow before aborting.

  Returns:
    A list of dicts with Value values.
  """
  return [dict(d) for d in _variable_product_items(variabledict.items(),
                                                   ComplexityLimit(limit))]


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
  discovered = set()  # Nodes found below some start node.

  # Start at a possible root and follow outgoing edges to update predecessors as
  # needed. Since the maximum number of times a given edge is processed is |V|,
  # the worst-case runtime is |V|*|E|. However, these graphs are typically
  # trees, so the usual runtime is much closer to |E|. Compared to using
  # Floyd-Warshall (|V|^3), this brings down the execution time on
  # pyglib/flags/flags_strict_test.py and pyglib/flags/flags_test.py
  # from about 30s to less than 7s.
  for start in nodes:
    if start in discovered:
      # We have already seen this node from a previous start, do nothing.
      continue
    unprocessed = [(start, n) for n in start.outgoing]
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
        discovered.add(node)

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

  # pylint: disable=unexpected-special-method-signature
  def __setitem__(self):
    raise TypeError()

  def __delitem__(self):
    raise TypeError()
  # pylint: enable=unexpected-special-method-signature

  def __hash__(self):
    return self._hash


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

  def delete_file(self, filename):
    os.unlink(os.path.join(self.path, filename))

  def __exit__(self, error_type, value, tb):
    shutil.rmtree(path=self.path)
    return False  # reraise any exceptions

  def __getitem__(self, filename):
    """Get the full path for an entry in this directory."""
    return os.path.join(self.path, filename)


@contextlib.contextmanager
def cd(path):
  """Context manager. Change the directory, and restore it afterwards.

  Example usage:
    with cd("/path"):
      ...

  Arguments:
    path: The directory to change to.
  Yields:
    Executes your code, in a changed directory.
  """
  curdir = os.getcwd()
  os.chdir(path)
  try:
    yield
  finally:
    os.chdir(curdir)


def load_pytype_file(filename):
  """Get the contents of a data file from the pytype installation.

  Arguments:
    filename: the path, relative to "pytype/"
  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  path = os.path.join(os.path.dirname(__file__), filename)
  with open(path, "rb") as fi:
    return fi.read()




def get_python_exe(python_version):
  """Automatically infer the --python_exe argument.

  Arguments:
    python_version: the version tuple (e.g. (2, 7))
  Returns:
    The inferred python_exe argument
  """
  python_exe = "python%d.%d" % python_version
  return python_exe


def is_valid_python_exe(python_exe):
  """Test that python_exe is a valid executable."""
  try:
    with open(os.devnull, "w") as null:
      subprocess.check_call(python_exe + " -V",
                            shell=True, stderr=null, stdout=null)
      return True
  except subprocess.CalledProcessError:
    return False


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


def invert_dict(d):
  """Invert a dictionary.

  Converts a dictionary (mapping strings to lists of strings) to a dictionary
  that maps into the other direction.

  Arguments:
    d: Dictionary to be inverted

  Returns:
    A dictionary n with the property that if "y in d[x]", then "x in n[y]".
  """

  inverted = collections.defaultdict(list)
  for key, value_list in d.items():
    for val in value_list:
      inverted[val].append(key)
  return inverted


class MonitorDict(dict):
  """A dictionary that monitors changes to its cfg.Variable values.

  This dictionary takes arbitrary objects as keys and cfg.Variable objects as
  values. It increments a changestamp whenever a new value is added or more data
  is merged into a value. The changestamp is unaffected by the addition of
  another origin for existing data.
  """

  def __init__(self, *args, **kwargs):
    super(MonitorDict, self).__init__(*args, **kwargs)

  def __delitem__(self, name):
    raise NotImplementedError

  def __setitem__(self, name, var):
    assert not dict.__contains__(self, name)
    super(MonitorDict, self).__setitem__(name, var)

  @property
  def changestamp(self):
    return len(self) + sum((len(var.bindings) for var in self.values()))

  @property
  def data(self):
    return itertools.chain.from_iterable(v.data for v in self.values())


class DictTemplate(dict):
  """A template class for dictionary subclasses.

  Use this template as a base for complex dictionary subclasses that
  should explicitly override dict methods that they wish to expose. A
  NotImplementedError is raised upon any attempt to access other methods.
  """

  def get(self, name):
    try:
      return self[name]
    except KeyError:
      return None

  def values(self):
    return super(DictTemplate, self).values()

  def items(self):
    return super(DictTemplate, self).items()

  def clear(self):
    raise NotImplementedError()

  def copy(self):
    raise NotImplementedError()

  def fromkeys(self):
    raise NotImplementedError()

  def has_key(self):
    raise NotImplementedError()

  def iteritems(self):
    raise NotImplementedError()

  def iterkeys(self):
    raise NotImplementedError()

  def itervalues(self):
    raise NotImplementedError()

  def keys(self):
    raise NotImplementedError()

  def pop(self):
    raise NotImplementedError()

  def popitem(self):
    raise NotImplementedError()

  def setdefault(self):
    raise NotImplementedError()

  def update(self):
    raise NotImplementedError()

  def viewitems(self):
    raise NotImplementedError()

  def viewkeys(self):
    raise NotImplementedError()

  def viewvalues(self):
    raise NotImplementedError()


class AliasingDictConflictError(Exception):

  def __init__(self, existing_name):
    super(AliasingDictConflictError, self).__init__()
    self.existing_name = existing_name


class AliasingDict(DictTemplate):
  """A dictionary that supports key aliasing.

  This dictionary provides a way to register aliases for a key, which are then
  treated like the key itself by getters and setters. It does not allow using
  a pre-existing key as an alias or adding the same alias to different keys.
  """

  def __init__(self, *args, **kwargs):
    self._alias_map = {}
    super(AliasingDict, self).__init__(*args, **kwargs)

  def add_alias(self, alias, name):
    """Alias 'alias' to 'name'."""
    assert alias not in self._alias_map.values()
    new_name = self._alias_map.get(name, name)
    existing_name = self._alias_map.get(alias, new_name)
    if new_name != existing_name:
      raise AliasingDictConflictError(existing_name)
    if super(AliasingDict, self).__contains__(alias):
      # This alias had a value, so move the value to the name that the alias
      # now points at.
      assert new_name not in self
      self[new_name] = self[alias]
      del self[alias]
    self._alias_map[alias] = new_name

  def __contains__(self, name):
    return super(AliasingDict, self).__contains__(
        self._alias_map.get(name, name))

  def __setitem__(self, name, var):
    super(AliasingDict, self).__setitem__(
        self._alias_map.get(name, name), var)

  def __getitem__(self, name):
    return super(AliasingDict, self).__getitem__(
        self._alias_map.get(name, name))

  def __repr__(self):
    return ("%r, _alias_map=%r" %
            (super(AliasingDict, self).__repr__(), repr(self._alias_map)))


class LazyDict(DictTemplate):
  """A dictionary that lazily adds and evaluates items.

  A value is evaluated and the (key, value) pair added to the
  dictionary when the user first tries to retrieve the value.
  """

  def __init__(self, *args, **kwargs):
    self._lazy_map = {}
    super(LazyDict, self).__init__(*args, **kwargs)

  def add_lazy_item(self, name, func, *args):
    assert callable(func)
    self._lazy_map[name] = (func, args)

  def lazy_eq(self, name, func, *args):
    """Do an approximate equality check for a lazy item without evaluating it.

    Returns True if the dictionary contains an already-evaluated value for the
    given key (since it's possible that if we evaluated the arguments, we'd get
    that value), or if the lazy map's entry for the key consists of the same
    function and arguments.

    Args:
      name: The key.
      func: The function that would be called to get the value.
      *args: The arguments to func.

    Returns:
      True if the item is (probably) in the dictionary, False if it is
      (probably) not.

    Raises:
      KeyError: If the given key is not in the dictionary.
    """
    if name in self:
      return name not in self._lazy_map or (func, args) == self._lazy_map[name]
    raise KeyError()

  def __getitem__(self, name):
    if not super(LazyDict, self).__contains__(name):
      func, args = self._lazy_map[name]
      self[name] = func(*args)
      del self._lazy_map[name]
    return super(LazyDict, self).__getitem__(name)

  def __len__(self):
    return super(LazyDict, self).__len__() + len(self._lazy_map)

  def __contains__(self, key):
    return super(LazyDict, self).__contains__(key) or key in self._lazy_map

  def __repr__(self):
    lazy_items = ("%r: %r(%r)" %
                  (name, func.func_name, ", ".join(repr(a) for a in args))
                  for name, (func, args) in self._lazy_map.items())
    return ("%r, _lazy_map={%r}" %
            (super(LazyDict, self).__repr__(), ", ".join(lazy_items)))

  def values(self):
    return [self[name] for name in set(self).union(self._lazy_map)]

  def items(self):
    return [(name, self[name]) for name in set(self).union(self._lazy_map)]


class LazyAliasingMonitorDict(LazyDict, AliasingDict, MonitorDict):
  pass


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
