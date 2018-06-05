"""Tests for dictionaries."""

from pytype.tests import test_base


class DictTest(test_base.TargetPython3BasicTest):
  """Tests for dictionaries."""

  def testFilteredGetItem(self):
    ty = self.Infer("""

      from typing import Union
      MAP = {0: "foo"}
      def foo(x: Union[int, None]):
        if x is not None:
          return MAP[x]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Union
      MAP = ...  # type: Dict[int, str]
      def foo(x: Union[int, None]) -> Any
    """)

  def testObjectInDict(self):
    errors = self.CheckWithErrors("""\

      from typing import Any, Dict
      def objectIsStr() -> Dict[str, Any]:
        return {object(): ""}
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type")])

  def testBigConcreteDict(self):
    # Test that we don't timeout.
    errorlog = self.CheckWithErrors("""\

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
        return d  # line 21
    """)
    self.assertErrorLogIs(errorlog, [(21, "bad-return-type")])

  def testDictOfTuple(self):
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


test_base.main(globals(), __name__ == "__main__")
