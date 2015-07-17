"""Test for running typegraphvm.py against StringIO.py."""

import os.path
from pytype.pytd import pytd
from pytype.tests import test_inference


class StringIOTests(test_inference.InferenceTest):

  def testDeep(self):
    with open(os.path.join(os.path.dirname(pytd.__file__),
                           "..", "test_data", "StringIO.py"), "rb") as fi:
      sourcecode = fi.read()
    # TODO(pludemann): This is similar to test_pytree.py ... combine them?
    # TODO(pludemann): extract_locals - see class test_inference.Infer
    with self.Infer(sourcecode, deep=True, solve_unknowns=True) as ty:
    # TODO(pludemann): change tests below to use function_names, class_names
    #                  as needed (they're currently unused)
      function_names = {f.name for f in ty.functions}
      class_names = {cls.name for cls in ty.classes}

      try:
        self.stringio_cls = ty.Lookup("StringIO")
      except KeyError:
        self.stringio_cls = None
        # Continue to the test -- it will fail if it needs the cls

      self.stringio_type = pytd.ClassType("StringIO")
      self.stringio_type.cls = self.stringio_cls

      self.assertHasOnlySignatures(ty.Lookup("_complain_ifclosed"),
                                   ((self.object,), self.none_type))

      self.assertIn("StringIO", class_names)

      self.assertHasOnlySignatures(self.stringio_cls.Lookup("__iter__"),
                                   ((self.stringio_type,), self.stringio_type))

      # TODO(rechen): We currently report ? rather than str for the return type
      # of StringIO.getvalue(), which is why assertHasSignature rather than
      # assertHasOnlySignatures is being used. Change this when
      # test_operators2.testAdd5 is working.
      self.assertHasSignature(self.stringio_cls.Lookup("getvalue"),
                              (self.stringio_type,), self.str)


if __name__ == "__main__":
  test_inference.main()
