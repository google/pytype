"""Test for running typegraphvm.py against pytree.py."""

import unittest

from pytype.pytd import utils as pytd_utils
from pytype.tests import test_inference


class PyTreeTests(test_inference.InferenceTest):

  def testDeep(self):
    sourcecode = pytd_utils.GetDataFile("examples/pytree.py")
    # TODO(pludemann): use new 'with' framework
    # TODO(pludemann): extract_locals - see class test_inference.Infer
    ty = self._InferAndVerify(sourcecode, deep=True)
    function_names = {f.name for f in ty.functions}
    class_names = {cls.name for cls in ty.classes}
    self.assertIn("type_repr", function_names)
    self.assertIn("Node", class_names)
    self.assertIn("Leaf", class_names)


if __name__ == "__main__":
  test_inference.main()
