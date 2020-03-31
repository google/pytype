"""Basic tests over Python 2.7 targets."""

from pytype.tests import test_base


class TestExec(test_base.TargetPython27FeatureTest):
  """The exec statement tests."""

  def test_exec_statement(self):
    self.assertNoCrash(self.Check, """
      g = {}
      exec "a = 11" in g, g
      assert g['a'] == 11
      """)


class TestPrinting(test_base.TargetPython27FeatureTest):
  """Printing tests."""

  def test_printing(self):
    self.Check("print 'hello'")
    self.Check("a = 3; print a+4")
    self.Check("""
      print 'hi', 17, u'bye', 23,
      print "", "\t", "the end"
      """)

  def test_printing_in_a_function(self):
    self.Check("""
      def fn():
        print "hello"
      fn()
      print "bye"
      """)

  def test_printing_to_a_file(self):
    self.Check("""
      import sys
      print >>sys.stdout, 'hello', 'there'
      """)


test_base.main(globals(), __name__ == "__main__")
