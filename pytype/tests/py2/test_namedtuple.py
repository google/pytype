"""Tests for the namedtuple implementation in collections_overlay.py."""

from pytype.tests import test_base


class NamedtupleTests(test_base.TargetPython27FeatureTest):
  """Tests for collections.namedtuple."""

  def test_calls(self):
    self.Check("""
        import collections
        collections.namedtuple("_", "")
        collections.namedtuple(typename="_", field_names="a")
        collections.namedtuple("_", "", True, False)
        """)
    self.assertNoCrash(self.Check, """
      collections.namedtuple(u"foo", [])
      collections.namedtuple(u"foo", [], replace=True if __random__ else False)
      collections.namedtuple(1.0, [])
      collections.namedtuple("foo", [1j, 2j])
      collections.namedtuple(__any_object__, __any_object__)
      collections.namedtuple(__any_object__, [__any_object__])
      """)

  def test_bad_call(self):
    _, errorlog = self.InferWithErrors("""\
        import collections
        collections.namedtuple()
        collections.namedtuple("_")
        collections.namedtuple("_", "", True, True, True)
        collections.namedtuple("_", "", True, verbose=True)
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "missing-parameter"),
                           (3, "missing-parameter"),
                           (4, "wrong-arg-count"),
                           (5, "duplicate-keyword-argument")])


test_base.main(globals(), __name__ == "__main__")
