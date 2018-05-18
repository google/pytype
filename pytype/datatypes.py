"""Generic data structures and collection classes."""

import itertools


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

  Use this template as a base for complex dictionary subclasses. Methods get(),
  values(), and items() are exposed; subclasses must explicitly override any
  other dict method that they wish to provide.
  """

  def get(self, name):
    # We reimplement get() because the builtin implementation doesn't play
    # nicely with AliasingDict.
    try:
      return self[name]
    except KeyError:
      return None

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
