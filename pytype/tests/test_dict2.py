"""Tests for dictionaries."""

from pytype.tests import test_base
from pytype.tests import test_utils


class DictTest(test_base.BaseTest):
  """Tests for dictionaries."""

  def test_filtered_getitem(self):
    ty = self.Infer("""
      from typing import Union
      MAP = {0: "foo"}
      def foo(x: Union[int, None]):
        if x is not None:
          return MAP[x]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional, Union
      MAP = ...  # type: Dict[int, str]
      def foo(x: Union[int, None]) -> Optional[str]: ...
    """)

  def test_object_in_dict(self):
    self.CheckWithErrors("""
      from typing import Any, Dict
      def objectIsStr() -> Dict[str, Any]:
        return {object(): ""}  # bad-return-type
    """)

  def test_big_concrete_dict(self):
    # Test that we don't timeout.
    self.CheckWithErrors("""
      from typing import Dict, Tuple, Union
      # A concrete dictionary with lots of concrete keys and a complicated
      # value type.
      d = {}
      ValueType = Dict[Union[str, int], Union[str, int]]
      v = ...  # type: ValueType
      d['a'] = v
      d['b'] = v
      d['c'] = v
      d['d'] = v
      d['e'] = v
      d[('a', None)] = v
      d[('b', None)] = v
      d[('c', None)] = v
      d[('d', None)] = v
      d[('e', None)] = v
      def f() -> Dict[Union[str, Tuple[str, None]], ValueType]:
        return d
      def g() -> Dict[int, int]:
        return d  # bad-return-type
    """)

  def test_dict_of_tuple(self):
    # utils.deep_variable_product(group_dict) generates a lot of combinations.
    # Test that we finish checking this code in a reasonable amount of time.
    self.Check("""
      from typing import Dict, Tuple
      def iter_equality_constraints(op):
        yield (op, 0 if __random__ else __any_object__)
      def get_equality_groups(ops) -> Dict[Tuple, Tuple]:
        group_dict = {}
        for op in ops:
          for a0 in iter_equality_constraints(op):
            group_dict[a0] = a0
            group_dict[__any_object__] = a0
        return group_dict
    """)

  def test_recursion(self):
    # Regression test for code that caused a RecursionError in STORE_SUBSCR.
    self.Check("""
      from typing import Any, Dict
      def convert(d: Dict[Any, Any]):
        keys = ['foo', 'bar']
        for key in keys:
          if key not in d:
            d[key + '_suffix1'] = {}
          if key + '_suffix2' in d:
            d[key + '_suffix1']['suffix2'] = d[key + '_suffix2']
          if key + '_suffix3' in d:
            d[key + '_suffix1']['suffix3'] = d[key + '_suffix3']
    """)

  @test_utils.skipBeforePy((3, 9), "Dict | was added in 3.9.")
  def test_union(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      a = {'a': 1} | {'b': 2}
      b = {'a': 1}
      b |= {1: 'a'}
      c: Dict[str, int] = {'a': 1} | {1: 'a'}  # annotation-type-mismatch
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      a: Dict[str, int]
      b: Dict[Union[str, int], Union[str, int]]
      c: Dict[str, int]
    """)

  @test_utils.skipBeforePy((3, 8), "Dict views are reversible in Python 3.8+.")
  def test_reverse_views(self):
    self.Check("""
      x = {'a': 'b'}
      print(reversed(x.keys()))
      print(reversed(x.values()))
      print(reversed(x.items()))
    """)

  def test_does_not_match_sequence(self):
    self.CheckWithErrors("""
      from typing import Sequence
      x: Sequence[str] = {1: 'a'}  # annotation-type-mismatch
      y: Sequence[str] = {'a': 1}  # annotation-type-mismatch
    """)


if __name__ == "__main__":
  test_base.main()
