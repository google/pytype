"""Test operators (basic tests)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class InplaceTest(test_base.BaseTest,
                  test_utils.InplaceTestMixin):
  """In-place operator tests."""

  def test_iadd(self):
    self._check_inplace("+", ["x=1", "y=2"], "int")
    self._check_inplace("+", ["x=1", "y=2j"], "complex")
    self._check_inplace("+", ["x='1'", "y='2'"], "str")
    self._check_inplace("+", ["x=[1]", "y=[2]"], "list[int]")
    self._check_inplace("+", ["x=[]", "y=[]"], "list[nothing]")
    self._check_inplace("+", ["x=[1]", "y=['abc']"], "list[int | str]")
    self._check_inplace("+", ["x=['']", "y=range(2)"], "list[int | str]")
    self._check_inplace("+", ["x=[1]", "y=iter(range(2))"], "list[int]")
    self._check_inplace("+", ["x=[1]", "y=(v for v in [2])"], "list[int]")
    self._check_inplace("+", ["x=(1,)", "y=(2,)"], "tuple[int, int]")
    self._check_inplace("+", ["x=(1,)", "y=(2.0,)"], "tuple[int, float]")

  def test_iand(self):
    self._check_inplace("&", ["x=3", "y=5"], "int")
    self._check_inplace("&", ["x={1}", "y={1, 2}"], "set[int]")
    self._check_inplace("&", ["x={1}", "y={1.2}"], "set[int]")
    self._check_inplace("&", ["x={1, 2}", "y=set([1])"], "set[int]")
    self._check_inplace("&", ["x=1", "y=2"], "int")

  def test_frozenset_ops(self):
    self._check_inplace("&", ["x=frozenset()", "y=frozenset()"],
                        "frozenset[nothing]")
    self._check_inplace("-", ["x=frozenset()", "y=frozenset()"],
                        "frozenset[nothing]")
    self._check_inplace("|", ["x=frozenset([1.0])", "y=frozenset([2.2])"],
                        "frozenset[float]")

  def test_ifloordiv(self):
    self._check_inplace("//", ["x=1", "y=2"], "int")
    self._check_inplace("//", ["x=1.0", "y=2"], "float")
    self._check_inplace("//", ["x=1j", "y=2j"], "complex")
    self._check_inplace("//", ["x=1.0", "y=2j"], "complex")

  def test_ilshift(self):
    self._check_inplace("<<", ["x=1", "y=2"], "int")

  def test_irshift(self):
    self._check_inplace(">>", ["x=1", "y=2"], "int")

  def test_isub(self):
    self._check_inplace("-", ["x=1", "y=2"], "int")
    self._check_inplace("-", ["x=1.0", "y=2"], "float")
    self._check_inplace("-", ["x=1j", "y=2j"], "complex")
    self._check_inplace("-", ["x={1}", "y={1, 2}"], "set[int]")
    self._check_inplace("-", ["x={1}", "y={1.2}"], "set[int]")

  def test_isub_frozenset(self):
    self._check_inplace("-", ["x={1, 2}", "y=frozenset([1.0])"], "set[int]")

  def test_imod(self):
    self._check_inplace("%", ["x=1", "y=2"], "int")
    self._check_inplace("%", ["x=1.5", "y=2.5"], "float")
    self._check_inplace("%", ["x='%r'", "y=set()"], "str")

  def test_imul(self):
    self._check_inplace("*", ["x=1", "y=2"], "int")
    self._check_inplace("*", ["x=1", "y=2.1"], "float")
    self._check_inplace("*", ["x=1+2j", "y=2.1+3.4j"], "complex")
    self._check_inplace("*", ["x='x'", "y=3"], "str")
    self._check_inplace("*", ["x=[1, 2]", "y=3"], "list[int]")
    self._check_inplace("*", ["x=99", "y=[1.0, 2]"], "list[int | float]")
    self._check_inplace("*", ["x=(1, 2)", "y=3"], "tuple[int, ...]")
    self._check_inplace("*", ["x=0", "y=(1, 2.0)"], "tuple[int | float, ...]")

  def test_ior(self):
    self._check_inplace("|", ["x=1", "y=2"], "int")
    self._check_inplace("|", ["x={1}", "y={2}"], "set[int]")

  def test_ipow(self):
    self._check_inplace("**", ["x=1", "y=2"], "int | float")
    self._check_inplace("**", ["x=1", "y=-2"], "int | float")
    self._check_inplace("**", ["x=1.0", "y=2"], "float")
    self._check_inplace("**", ["x=1", "y=2.0"], "float")
    self._check_inplace("**", ["x=1.1", "y=2.1"], "float")
    self._check_inplace("**", ["x=1j", "y=2j"], "complex")

  def test_ixor(self):
    self._check_inplace("^", ["x=1", "y=2"], "int")
    self._check_inplace("^", ["x={1}", "y={2}"], "set[int]")

  def test_setitem_and_iadd(self):
    self.Check("""
      from typing import Dict, TypeVar
      T = TypeVar('T')
      class Item:
        pass
      class ItemDict(Dict[Item, T]):
        def __setitem__(self, k: Item, v: T):
          if not v.id:
            raise ValueError()
          super().__setitem__(k, v)
        def __iadd__(self, other: 'ItemDict'):
          for k, v in other.items():
            self[k] += v
          return self
        def Add(self, value: T):
          super().__setitem__(value.id, value)
    """)


if __name__ == "__main__":
  test_base.main()
