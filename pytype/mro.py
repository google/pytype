"""Generic functions with non-stdlib dependencies."""


from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils


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
  bases = utils.concat_lists(b.data for b in c.bases())
  return tuple(pytd_utils.MROMerge([[c]] +
                                   [list(base.mro) for base in bases] +
                                   [list(bases)]))
