"""Test list, dict, etc."""

import unittest
from pytype.pytd import pytd
from pytype.tests import test_inference


class ContainerTest(test_inference.InferenceTest):

  def testTuplePassThrough(self):
    with self.Infer("""
      def f(x):
        return x
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
           pytd.HomogeneousContainerType(self.tuple, (self.intorstr,))))

  def testTuple(self):
    with self.Infer("""
      def f(x):
        return x[0]
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
           self.intorstr))

  def testTupleSwap(self):
    with self.Infer("""
      def f(x):
        return (x[1], x[0])
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
           pytd.HomogeneousContainerType(self.tuple, (self.intorstr,))))

  def testEmptyTuple(self):
    with self.Infer("""
      def f():
        return ()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(self.tuple, (pytd.NothingType(),))))

  def testSetsSanity(self):
    with self.Infer("""
      def f():
        x = set([1])
        x.add(10)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(pytd.ClassType("set"), (self.int,))))

  def testSetsAdd(self):
    with self.Infer("""
      def f():
        x = set([])
        x.add(1)
        x.add(10)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(pytd.ClassType("set"), (self.int,))))

  def testSets(self):
    with self.Infer("""
      def f():
        x = set([1,2,3])
        if x:
          x = x | set()
          y = x
          return x
        else:
          x.add(10)
          return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(pytd.ClassType("set"), (self.int,))))

  def testListLiteral(self):
    with self.Infer("""
      def f():
        return [1, 2, 3]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListAppend(self):
    with self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListConcat(self):
    with self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return [0] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListConcatMultiType(self):
    with self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append("str")
        return x + [1.3] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((),
           pytd.HomogeneousContainerType(
               self.list,
               (pytd.UnionType((self.int, self.float, self.str)),))))

  def testListConcatUnlike(self):
    with self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return ["str"] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), pytd.HomogeneousContainerType(self.list, (self.intorstr,))))

  def testAnyObject(self):
    with self.Infer("""
      def f():
        return __any_object__
      def g():
        return __any_object__()
      def h():
        return __any_object__("name")
      f(); g(); h()
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"), ((), self.anything))
      self.assertHasOnlySignatures(ty.Lookup("g"), ((), self.anything))
      self.assertHasOnlySignatures(ty.Lookup("h"), ((), self.anything))

  def testDictLiteral(self):
    with self.Infer("""
      def f():
        return {"test": 1, "arg": 42}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), self.str_int_dict))

  def testDictEmptyConstructor(self):
    with self.Infer("""
      def f():
        return dict()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), self.nothing_nothing_dict))

  def testDictConstructor(self):
    with self.Infer("""
      def f():
        return dict([(1, 2), (3, 4)])
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), self.int_int_dict))

  @unittest.skip("Needs more precise support for tuples")
  def testDictConstructor2(self):
    with self.Infer("""
      def f():
        return dict([(1, "bar"), (2, "foo")])
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), self.int_str_dict))

  def testDictUpdate(self):
    with self.Infer("""
      def f():
        d = {}
        d["test"] = 1
        d["arg"] = 42
        return d
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(
          ty.Lookup("f"),
          ((), self.str_int_dict))

  def testForIter(self):
    with self.Infer("""
      class A:
        def __init__(self):
          self.parent = "foo"

      def set_parent(l):
        for e in l:
          e.parent = 1

      def f():
        a = A()
        b = A()
        set_parent([a, b])
        return a.parent

      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.intorstr))

  def testOverloading(self):
    with self.Infer("""
      class Base(object):
        parent = None
        children = ()
        def bar(self, new):
            for ch in self.parent.children:
                ch.foobar = 3

      class Node(Base):
        def __init__(self, children):
          self.children = list(children)
          for ch in self.children:
            ch.parent = self

      class Leaf(Base):
        def __init__(self):
          pass

      def f():
        l1 = Leaf()
        l2 = Leaf()
        n1 = Node([l1, l2])
        l2.bar(None)
        return l2.foobar

      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.int))

  def testClassAttr(self):
    with self.Infer("""
      class Node(object):
        children = ()

      def f():
        n1 = Node()
        n1.children = [n1]
        for ch in n1.children:
          ch.foobar = 3
        return n1.foobar

      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.int))

  def testHeterogeneous(self):
    with self.Infer("""
      def f():
        x = list()
        x.append(3)
        x.append("str")
        return x[0]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.intorstr))

  def testListComprehension(self):
    # uses byte_LIST_APPEND
    with self.Infer("""
      def f():
        return [i for i in (1,2,3)]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.int_list))

  def testSetComprehension(self):
    # uses byte_SET_ADD
    with self.Infer("""
      def f():
        return {i for i in [1,2,3]}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.int_set))

  def testDictComprehension(self):
    # uses byte_MAP_ADD
    with self.Infer("""
      def f():
        return {i: i for i in xrange(3)}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((),
                                    self.int_int_dict))

  def testLeakingType(self):
    with self.Infer("""
      import sys
      a = [str(ty) for ty in (int, bool)[:len(sys.argv)]]
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        sys: module
        a: list<str>
        ty: type
      """)


if __name__ == "__main__":
  test_inference.main()
