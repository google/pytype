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
    assert not dict.__contains__(self, name)
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
  treated like the key itself by getters and setters. It does not allow using
  a pre-existing key as an alias or adding the same alias to different keys. To
  avoid surprising behavior, we raise NotImplementedError for all dict methods
  not explicitly supported; supported methods are get(), values(), and items().
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
      if new_name in self:
        # The alias and the name it now points at both have values; we can't
        # reconcile the two.
        raise AliasingDictConflictError(new_name)
      else:
        # Move the alias's value to the name that the alias now points at.
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

  def get(self, name):
    # We reimplement get() because the builtin implementation doesn't play
    # nicely with aliasing.
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


class AliasingMonitorDict(AliasingDict, MonitorDict):
  pass


# Based on https://docs.python.org/3/library/types.html#types.SimpleNamespace
# and can be replaced with types.SimpleNamespace when we drop Python 2 support.
class SimpleNamespace(object):
  """A simple object class that provides attribute access to its namespace."""

  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)
