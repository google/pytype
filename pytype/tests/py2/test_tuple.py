"""Tests of __builtin__.tuple."""

from pytype.tests import test_base


class TupleTest(test_base.TargetPython27FeatureTest):
  """Tests for __builtin__.tuple."""

  def test_iteration(self):
    ty = self.Infer("""
      class Foo(object):
        mytuple = (1, "foo", 3j)
        def __getitem__(self, pos):
          return Foo.mytuple.__getitem__(pos)
      r = [x for x in Foo()]  # Py 2 leaks 'x'
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, Union
      class Foo(object):
        mytuple = ...  # type: Tuple[int, str, complex]
        def __getitem__(self, pos: int) -> Union[int, str, complex]: ...
      x = ...  # type: Union[int, str, complex]
      r = ...  # type: List[Union[int, str, complex]]
    """)


test_base.main(globals(), __name__ == "__main__")
