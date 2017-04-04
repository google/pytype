"""Python code corresponding to PYTHONCODE entries in __builtin__.pytd.

Each PYTHONCODE item in __builtin__.pytd will have a single python `def` here.
"""


# pylint: disable=redefined-builtin
# pylint: disable=invalid-name
# pylint: disable=unused-argument
# pylint: disable=undefined-variable


def abs(number):
  return number.__abs__()


def cmp(x, y):
  return True


def repr(x):
  return ''


def next(iterator, default=__undefined__):
  if __random__:
    return iterator.next()
  else:
    return default


class property(object):
  """Property method decorator."""

  def __init__(self, fget=None, fset=None, fdel=None, doc=None):
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    self.__doc__ = doc

  def __get__(self, obj, objtype):
    return self.fget(obj)

  def __set__(self, obj, value):
    return self.fset(obj, value)

  def __delete__(self, obj):
    return self.fdel(obj)

  def getter(self, fget):
    return property(fget, self.fset, self.fdel, self.__doc__)

  def setter(self, fset):
    return property(self.fget, fset, self.fdel, self.__doc__)

  def deleter(self, fdel):
    return property(self.fget, self.fset, fdel, self.__doc__)


class staticmethod(object):
  """Staticmethod method decorator."""

  def __init__(self, func):
    # Name the inner method __func__, like in Python/Objects/funcobject.c
    self.__func__ = func

  def __get__(self, obj, objtype):
    return self.__func__


class classmethod(object):
  """Classmethod method decorator."""

  def __init__(self, func):
    # Name the inner method __func__, like in Python/Objects/funcobject.c
    self.__func__ = func

  def __get__(self, obj, objtype):
    func = self.__func__
    def method(*args, **kwargs):
      return func(objtype, *args, **kwargs)
    return method
