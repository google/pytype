"""Tests for the namedtuple implementation in collections_overlay.py."""

from pytype.tests import test_base


class NamedtupleTests(test_base.TargetPython3BasicTest):
  """Tests for collections.namedtuple."""

  def test_namedtuple_match(self):
    self.Check("""
        import collections
        from typing import Any, Dict

        X = collections.namedtuple("X", ["a"])

        def GetRefillSeekerRanks() -> Dict[str, X]:
          return {"hello": X(__any_object__)}
        """)


class NamedtupleTestsPy3(test_base.TargetPython3FeatureTest):
  """Tests for collections.namedtuple in Python 3."""

  def test_bad_call(self):
    """The last two arguments are kwonly in 3.6."""
    self.InferWithErrors("""
        import collections
        collections.namedtuple()  # missing-parameter
        collections.namedtuple("_")  # missing-parameter
        collections.namedtuple("_", "", True)  # wrong-arg-count
        collections.namedtuple("_", "", True, True)  # wrong-arg-count
        collections.namedtuple("_", "", True, True, True)  # wrong-arg-count
    """)


test_base.main(globals(), __name__ == "__main__")
