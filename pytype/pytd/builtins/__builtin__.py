"""Python code corresponding to PYTHONCODE entries in __builtin__.pytd.

Each PYTHONCODE item in __builtin__.pytd will have a single python `def` here.
"""


# pylint: disable=redefined-builtin
# pylint: disable=invalid-name
# pylint: disable=unused-argument


def abs(number):
  return number.__abs__()


# TODO(pludemann): Use the proper definition of cmp (similar to repr)
def cmp(x, y):
  return True


# TODO(pludemann): Use the proper definition of repr (see TODO.txt)
def repr(x):
  return ''


class property(object):
  """Property method decorator."""
  # TODO(kramm): Support for setter(), getter(), deleter()

  def __init__(self, fget, fset=None, fdel=None, doc=None):
    self.fget = fget
    self.fset = fset
    self.fdel = fdel
    self.doc = doc

  def __get__(self, obj, objtype):
    return self.fget(obj)

  def __set__(self, obj, value):
    return self.fset(obj, value)

  def __delete__(self, obj):
    return self.fdel(obj)


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
