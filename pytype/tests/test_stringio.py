"""Test for running typegraphvm.py against pytree.py."""


import unittest
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.tests import test_inference


class StringIOTests(test_inference.InferenceTest):

  @unittest.skip("Temporarily disabled. Takes > 162 sec (infinite loop?)")
  def testDeep(self):
    sourcecode = pytd_utils.GetDataFile("examples/StringIO.py")
    # TODO(pludemann): This is similar to test_pytree.py ... combine them?
    # TODO(pludemann): use new 'with' framework
    # TODO(pludemann): extract_locals - see class test_inference.Infer
    ty = self._InferAndVerify(sourcecode, deep=True, expensive=False)
    # TODO(pludemann): change tests below to use function_names, class_names
    #                  as needed (they're currently unused)
    function_names = {f.name for f in ty.functions}
    class_names = {cls.name for cls in ty.classes}

    try:
      self.stringio_cls = self.ty.Lookup("StringIO")
    except KeyError:
      self.stringio_cls = None
      # Continue to the test -- it will fail if it needs the cls

    self.stringio_type = pytd.ClassType("StringIO")
    self.stringio_type.cls = self.stringio_cls

    self.assertHasOnlySignatures(self.ty.Lookup("_complain_ifclosed"),
                                 ((self.bool,), self.none_type))

    self.assertIn("StringIO", self.ty.classes)

    self.assertHasOnlySignatures(self.stringio_cls.Lookup("__iter__"),
                                 ((self.stringio_type,), self.stringio_type))

    self.assertHasOnlySignatures(self.stringio_cls.Lookup("get_value"),
                                 ((self.stringio_type,), self.str))


if __name__ == "__main__":
  test_inference.main()
