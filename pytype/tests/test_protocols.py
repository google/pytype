"""Tests for matching against protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""

from pytype.tests import test_base


class ProtocolTest(test_base.TargetIndependentTest):
  """Tests for protocol implementation."""

  def test_use_iterable(self):
    ty = self.Infer("""
      class A(object):
        def __iter__(self):
          return iter(__any_object__)
      v = list(A())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        def __iter__(self) -> Any: ...
      v = ...  # type: list
    """)


test_base.main(globals(), __name__ == "__main__")
