"""Test for running typegraphvm.py against pytree.py."""


import unittest

from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.tests import test_inference


@unittest.skip("Temporarily disabled. Needs --deep")
# Also uses old form of self.Infer; needs to be change to 'with self.Infer'
class StringIOTests(test_inference.InferenceTest):

  def setUp(self):
    with open(utils.GetDataFile("examples/StringIO.py"), "r") as infile:
      self.ty = self.Infer(infile.read())
    try:
      self.stringio_cls = self.ty.Lookup("StringIO")
    except KeyError:
      self.stringio_cls = None
      # Continue to the test it will fail if it needs the cls
    self.stringio_type = pytd.ClassType("StringIO")
    self.stringio_type.cls = self.stringio_cls

  def testComplainIfclosed(self):
    self.assertHasOnlySignatures(self.ty.Lookup("_complain_ifclosed"),
                                 ((self.bool), self.none_type))

  def testClassesExist(self):
    self.assertIn("StringIO", self.ty.classes)

  def testStringIOIter(self):
    self.assertHasOnlySignatures(self.stringio_cls.Lookup("__iter__"),
                                 ((self.stringio_type), self.stringio_type))

  def testStringIOGetValue(self):
    self.assertHasOnlySignatures(self.stringio_cls.Lookup("get_value"),
                                 ((self.stringio_type), self.str))


if __name__ == "__main__":
  test_inference.main()
