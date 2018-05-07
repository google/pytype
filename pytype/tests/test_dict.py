"""Tests for dictionaries."""

from pytype.tests import test_base


class DictTest(test_base.TargetIndependentTest):
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

  def testPop(self):
    ty = self.Infer("""
      d = {"a": 42}
      v1 = d.pop("a")
      v2 = d.pop("b", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, int]
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)

  def testBadPop(self):
    ty, errors = self.InferWithErrors("""\
      d = {"a": 42}
      v = d.pop("b")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      d = ...  # type: Dict[str, int]
      v = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "key-error", r"b")])

  def testAmbiguousPop(self):
    ty = self.Infer("""
      d = {"a": 42}
      k = None  # type: str
      v1 = d.pop(k)
      v2 = d.pop(k, None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def testPopFromAmbiguousDict(self):
    ty = self.Infer("""
      d = {}
      k = None  # type: str
      v = None  # type: int
      d[k] = v
      v1 = d.pop("a")
      v2 = d.pop("a", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v = ...  # type: int
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def testObjectInDict(self):
    errors = self.CheckWithErrors("""\
            from typing import Any, Dict
      def objectIsStr() -> Dict[str, Any]:
        return {object(): ""}
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type")])

  def testUpdateEmpty(self):
    ty = self.Infer("""
      from typing import Dict
      d1 = {}
      d2 = None  # type: Dict[str, int]
      d1.update(d2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[str, int]
      d2 = ...  # type: Dict[str, int]
    """)

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


if __name__ == "__main__":
  test_base.main()
