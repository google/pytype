"""Test cases that match the workflow doc."""

from pytype.tests import test_inference


class WorkflowTest(test_inference.InferenceTest):

  def testWorkflow1(self):
    with self.Infer("""
      class ConfigParser(object):
        def __init__(self, filename):
          self.filename = filename
        def read(self):
          with open(self.filename, "r") as fi:
            return fi.read()

      cp = ConfigParser(__any_object__())
      cp.read()
      """, deep=False, solve_unknowns=True, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        cp = ...  # type: ConfigParser

        class ConfigParser:
          # TODO(pludemann): remove '-> NoneType'
          def __init__(self, filename: str or bytes or buffer or unicode) -> NoneType
          def read(self) -> str
          filename = ...  # type: str or bytes or buffer or unicode
      """)

if __name__ == '__main__':
  test_inference.main()
