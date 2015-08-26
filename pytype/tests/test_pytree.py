"""Test for running typegraphvm.py against pytree.py."""

import os.path
from pytype.pytd import pytd
from pytype.tests import test_inference


class PyTreeTests(test_inference.InferenceTest):

  def testDeep(self):
    with open(os.path.join(os.path.dirname(pytd.__file__),
                           "..", "test_data", "pytree.py"), "rb") as fi:
      sourcecode = fi.read()
    # TODO(pludemann): extract_locals - see class test_inference.Infer
    # TODO(pludemann): ? solve_unknowns=True ?
    with self.Infer(sourcecode, deep=True, report_errors=False) as ty:
      function_names = {f.name for f in ty.functions}
      class_names = {cls.name for cls in ty.classes}
      self.assertIn("type_repr", function_names)
      self.assertIn("Node", class_names)
      self.assertIn("Leaf", class_names)


if __name__ == "__main__":
  test_inference.main()
