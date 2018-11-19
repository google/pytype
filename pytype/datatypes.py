"""Generic data structures and collection classes."""

import itertools


class UnionFind(object):
  r"""A disjoint-set data structure for `AliasingDict`.

  This is used to record the alias information for `AliasingDict`. It is
  consist of different components. Each component will contain the names
  that represent the same thing.
    E.g., for a five-node component/tree, the representative for all the
    nodes in the component is `T`:
       T          [T] The root node and representative
      / \         [U] Its parent is `T`
     U   V        [V] Its parent is `T`
        / \       [W] Its parent is `V`
       W   X      [X] Its parent is `V`
  For performance consideration, we will compress the path each time when
  we compute the representative of a node. E.g., if we try to get the
  representative of node `W`, then the above tree will become:
      T
     /|\
    U W V
         \
          X


  Attributes:
    name2id: mapping all names to unique id.
    parent: the parent id of current unique id.
    rank: the height of the tree for corresponding component, it is an
    optimization to merge two components.
    id2name: mapping unique id to corresponding names, the reverse map of
    `name2id`.
    latest_id: the maximal allocated id.
  """

  def __init__(self):
    self.name2id = {}
    self.parent = []
    self.rank = []
    self.id2name = []
    self.latest_id = 0

  def copy(self):
    res = UnionFind()
    res.name2id = self.name2id.copy()
    res.parent = list(self.parent)
    res.rank = list(self.rank)
    res.id2name = list(self.id2name)
    res.latest_id = self.latest_id
    return res

  def merge_from(self, uf):
    """Merge a UnionFind into the current one."""
    for i, name in enumerate(uf.id2name):
      self.merge(name, uf.id2name[uf.parent[i]])

  def find_by_name(self, name):
    """Find the representative of a component represented by given name."""
    key = self._get_or_add_id(name)
    return self.id2name[self._find(key)]

  def merge(self, name1, name2):
    """Merge two components represented by the given names."""
    key1 = self._get_or_add_id(name1)
    key2 = self._get_or_add_id(name2)
    self._merge(key1, key2)
    return self.find_by_name(name1)

  def _get_or_add_id(self, name):
    if name not in self.name2id:
      self.name2id[name] = self.latest_id
      self.parent.append(self.latest_id)
      self.rank.append(1)
      self.id2name.append(name)
      self.latest_id += 1
    return self.name2id[name]

  def _find(self, key):
    """Find the tree root."""
    assert self.latest_id > key
    res = key
    if self.parent[key] != key:
      res = self._find(self.parent[key])
      # Compress/Optimize the search path
      self.parent[key] = res
    return res

  def _merge(self, k1, k2):
    """Merge two components."""
    assert self.latest_id > k1 and self.latest_id > k2
    s1 = self._find(k1)
    s2 = self._find(k2)
    if s1 != s2:
      if self.rank[s1] > self.rank[s2]:
        self.parent[s2] = s1
      elif self.rank[s1] < self.rank[s2]:
        self.parent[s1] = s2
      else:
        self.parent[s1] = s2
        self.rank[s2] += 1

  def __repr__(self):
    comps = []
    used = set()
    for x in self.id2name:
      if x not in used:
        comp = []
        for y in self.id2name:
          if self.find_by_name(x) == self.find_by_name(y):
            used.add(y)
            comp.append(y)
        comps.append(comp)
    return "%r" % comps


class AccessTrackingDict(dict):
  """A dict that tracks access of its original items."""

  def __init__(self, d):
    super(AccessTrackingDict, self).__init__(d)
    self.accessed_subset = {}

  def __getitem__(self, k):
    v = super(AccessTrackingDict, self).__getitem__(k)
    if k not in self.accessed_subset:
      self.accessed_subset[k] = v
    return v

  def __setitem__(self, k, v):
    if k in self:
      _ = self[k]
    # If the key is new, we don't track it.
    return super(AccessTrackingDict, self).__setitem__(k, v)

  def __delitem__(self, k):
    if k in self:
      _ = self[k]
    return super(AccessTrackingDict, self).__delitem__(k)


class MonitorDict(dict):
  """A dictionary that monitors changes to its cfg.Variable values.

  This dictionary takes arbitrary objects as keys and cfg.Variable objects as
  values. It increments a changestamp whenever a new value is added or more data
  is merged into a value. The changestamp is unaffected by the addition of
  another origin for existing data.
  """

  def __delitem__(self, name):
    raise NotImplementedError

  def __setitem__(self, name, var):
    super(MonitorDict, self).__setitem__(name, var)

  @property
  def changestamp(self):
    return len(self) + sum((len(var.bindings) for var in self.values()))

  @property
  def data(self):
    return itertools.chain.from_iterable(v.data for v in self.values())


class AliasingDictConflictError(Exception):

  def __init__(self, existing_name):
    super(AliasingDictConflictError, self).__init__()
    self.existing_name = existing_name


class AliasingDict(dict):
  """A dictionary that supports key aliasing.

  This dictionary provides a way to register aliases for a key, which are then
  treated like the key itself by getters and setters. To avoid surprising
  behavior, we raise NotImplementedError for all dict methods not explicitly
  supported; supported methods are get(), values(), items(), copy() and keys().
  """

  def __init__(self, *args, **kwargs):
    self._uf = UnionFind()
    super(AliasingDict, self).__init__(*args, **kwargs)

  @property
  def uf(self):
    return self._uf

  @uf.setter
  def uf(self, uf):
    self._uf = uf

  def copy(self):
    res = AliasingDict()
    res.uf = self.uf.copy()
    for k, v in self.items():
      res[k] = v
    return res

  def add_alias(self, alias, name, op=None):
    """Alias 'alias' to 'name'.

    After aliasing, we will think `alias` and `name`, they represent the same
    name. We will merge the values if `op` is provided.

    Args:
      alias: A string.
      name: A string.
      op: The function used to merge the values.
    """
    alias = self.uf.find_by_name(alias)
    name = self.uf.find_by_name(name)
    if alias == name:  # Already in one component
      return
    elif alias in self and name in self:
      # Merge the values if `op` operator is provided
      val = op(self[alias], self[name]) if op else self[alias]
      del self[alias]
      del self[name]
      root = self.uf.merge(alias, name)
      self[root] = val
    elif alias not in self and name not in self:
      self.uf.merge(alias, name)
    elif alias in self:
      root = self.uf.merge(alias, name)
      self[root] = dict.__getitem__(self, alias)
      if alias != root: dict.__delitem__(self, alias)
    elif name in self:
      root = self.uf.merge(alias, name)
      self[root] = dict.__getitem__(self, name)
      if name != root: dict.__delitem__(self, name)

  def same_name(self, name1, name2):
    return self.uf.find_by_name(name1) == self.uf.find_by_name(name2)

  def __contains__(self, name):
    return super(AliasingDict, self).__contains__(self.uf.find_by_name(name))

  def __setitem__(self, name, var):
    super(AliasingDict, self).__setitem__(self.uf.find_by_name(name), var)

  def __getitem__(self, name):
    return super(AliasingDict, self).__getitem__(self.uf.find_by_name(name))

  def __repr__(self):
    return ("%r, _alias=%r" %
            (super(AliasingDict, self).__repr__(), repr(self.uf)))

  def __hash__(self):
    return hash(frozenset(self.items()))

  def get(self, name, default=None):
    # We reimplement get() because the builtin implementation doesn't play
    # nicely with aliasing.
    try:
      return self[name]
    except KeyError:
      return default

  def clear(self):
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


class HashableDict(AliasingDict):
  """A AliasingDict subclass that can be hashed.

  Instances should not be modified. Methods that would modify the dictionary
  have been overwritten to throw an exception.
  """

  def __init__(self, alias_dict=None):
    if alias_dict:
      super(HashableDict, self).__init__(alias_dict)
      self.uf = alias_dict.uf
    else:
      super(HashableDict, self).__init__()
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


class AliasingMonitorDict(AliasingDict, MonitorDict):
  """The dictionary that supports aliasing, lazy dict and monitor."""

  def merge_from(self, lam_dict, op):
    """Merge the other `AliasingMonitorDict` into current class.

    Args:
      lam_dict: The dict to merge from.
      op: The function used to merge the values.
    """
    # Merge from dict
    for key, val in lam_dict.items():
      if key in self:
        self[key] = op(self[key], val, key)
      else:
        self[key] = val
    # Merge the aliasing info
    for cur_id in range(lam_dict.uf.latest_id):
      parent_id = lam_dict.uf.parent[cur_id]
      cur_name = lam_dict.uf.id2name[cur_id]
      parent_name = lam_dict.uf.id2name[parent_id]
      if self.uf.find_by_name(cur_name) != self.uf.find_by_name(parent_name):
        self.add_alias(cur_name, parent_name, op)

  def _merge(self, name1, name2, op):
    name1 = self.uf.find_by_name(name1)
    name2 = self.uf.find_by_name(name2)
    assert name1 != name2
    self[name1] = op(self[name1], self[name2], name1)
    dict.__delitem__(self, name2)
    root = self.uf.merge(name1, name2)
    self._copy_item(name1, root)

  def _copy_item(self, src, tgt):
    """Assign the dict `src` value to `tgt`."""
    if src == tgt:
      return
    self[tgt] = dict.__getitem__(self, src)
    dict.__delitem__(self, src)

  def add_alias(self, alias, name, op):
    alias = self.uf.find_by_name(alias)
    name = self.uf.find_by_name(name)
    if alias == name:
      return
    elif alias in self and name in self:
      self._merge(alias, name, op)
    elif alias not in self and name not in self:
      self.uf.merge(alias, name)
    elif alias in self:
      root = self.uf.merge(alias, name)
      self._copy_item(alias, root)
    elif name in self:
      root = self.uf.merge(alias, name)
      self._copy_item(name, root)


# Based on https://docs.python.org/3/library/types.html#types.SimpleNamespace
# and can be replaced with types.SimpleNamespace when we drop Python 2 support.
class SimpleNamespace(object):
  """A simple object class that provides attribute access to its namespace."""

  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)
