"""Tests for inferring protocols."""

from pytype.tests import test_base


class ProtocolInferenceTest(test_base.TargetPython27FeatureTest):
  """Tests for protocol implementation."""

  def test_workflow(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""
      class ConfigParser(object):
        def __init__(self, filename):
          self.filename = filename
        def read(self):
          with open(self.filename, "r") as fi:
            return fi.read()

      cp = ConfigParser(__any_object__())
      cp.read()
      """, deep=False)
    self.assertTypesMatchPytd(ty, """
      cp = ...  # type: ConfigParser

      class ConfigParser(object):
        def __init__(self, filename: str or buffer or unicode) -> NoneType
        def read(self) -> str
        filename = ...  # type: str or buffer or unicode
    """)


if __name__ == "__main__":
  test_base.main()
