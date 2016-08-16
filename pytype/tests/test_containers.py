"""Test list, dict, etc."""

import unittest
from pytype.pytd import pytd
from pytype.tests import test_inference


class ContainerTest(test_inference.InferenceTest):

  def testTuplePassThrough(self):
    ty = self.Infer("""
      def f(x):
        return x
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
         pytd.HomogeneousContainerType(self.tuple, (self.intorstr,))))

  def testTuple(self):
    ty = self.Infer("""
      def f(x):
        return x[0]
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
         self.intorstr))

  def testTupleSwap(self):
    ty = self.Infer("""
      def f(x):
        return (x[1], x[0])
      f((3, "str"))
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.HomogeneousContainerType(self.tuple, (self.intorstr,)),),
         pytd.HomogeneousContainerType(self.tuple, (self.intorstr,))))

  def testEmptyTuple(self):
    ty = self.Infer("""
      def f():
        return ()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.tuple, (pytd.NothingType(),))))

  def testSetsSanity(self):
    ty = self.Infer("""
      def f():
        x = set([1])
        x.add(10)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.set, (self.int,))))

  def testSetsAdd(self):
    ty = self.Infer("""
      def f():
        x = set([])
        x.add(1)
        x.add(10)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.set, (self.int,))))

  def testSets(self):
    ty = self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.set, (self.int,))))

  def testListLiteral(self):
    ty = self.Infer("""
      def f():
        return [1, 2, 3]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListAppend(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListConcat(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return [0] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.list, (self.int,))))

  def testListConcatMultiType(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append("str")
        return x + [1.3] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((),
         pytd.HomogeneousContainerType(
             self.list,
             (pytd.UnionType((self.int, self.float, self.str)),))))

  def testUnionIntoTypeParam(self):
    ty = self.Infer("""
      y = __any_object__
      if y:
        x = 3
      else:
        x = 3.1
      l = []
      l.append(x)
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int or float
      y = ...  # type: ?
      l = ...  # type: List[int or float, ...]
    """)

  def testListConcatUnlike(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return ["str"] + x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.HomogeneousContainerType(self.list, (self.intorstr,))))

  def testAnyObject(self):
    ty = self.Infer("""
      def f():
        return __any_object__
      def g():
        return __any_object__()
      def h():
        return __any_object__("name")
      f(); g(); h()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertHasOnlySignatures(ty.Lookup("f"), ((), self.anything))
    self.assertHasOnlySignatures(ty.Lookup("g"), ((), self.anything))
    self.assertHasOnlySignatures(ty.Lookup("h"), ((), self.anything))

  def testDictLiteral(self):
    ty = self.Infer("""
      def f():
        return {"test": 1, "arg": 42}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.str_int_dict))

  def testDictEmptyConstructor(self):
    ty = self.Infer("""
      def f():
        return dict()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.nothing_nothing_dict))

  def testDictConstructor(self):
    ty = self.Infer("""
      def f():
        return dict([(1, 2), (3, 4)])
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.int_int_dict))

  @unittest.skip("Needs more precise support for tuples")
  def testDictConstructor2(self):
    ty = self.Infer("""
      def f():
        return dict([(1, "bar"), (2, "foo")])
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.int_str_dict))

  def testDictUpdate(self):
    ty = self.Infer("""
      def f():
        d = {}
        d["test"] = 1
        d["arg"] = 42
        return d
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.str_int_dict))

  def testForIter(self):
    ty = self.Infer("""
      class A(object):
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.intorstr))

  def testOverloading(self):
    ty = self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int))

  def testClassAttr(self):
    ty = self.Infer("""
      class Node(object):
        children = ()

      def f():
        n1 = Node()
        n1.children = [n1]
        for ch in n1.children:
          ch.foobar = 3
        return n1.foobar

      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int))

  def testHeterogeneous(self):
    ty = self.Infer("""
      def f():
        x = list()
        x.append(3)
        x.append("str")
        return x[0]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.intorstr))

  def testListComprehension(self):
    # uses byte_LIST_APPEND
    ty = self.Infer("""
      def f():
        return [i for i in (1,2,3)]
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_list))

  def testSetComprehension(self):
    # uses byte_SET_ADD
    ty = self.Infer("""
      def f():
        return {i for i in [1,2,3]}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_set))

  def testDictComprehension(self):
    # uses byte_MAP_ADD
    ty = self.Infer("""
      def f():
        return {i: i for i in xrange(3)}
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_int_dict))

  def testLeakingType(self):
    ty = self.Infer("""
      import sys
      a = [str(ty) for ty in (int, bool)[:len(sys.argv)]]
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      a = ...  # type: List[str, ...]
      ty = ...  # type: type
    """)

  def testEmptyOrString(self):
    ty = self.Infer("""
      d = dict()
      d["a"] = "queen"
      entry = d["a"]
      open('%s' % entry, 'w')
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      d = ...  # type: Dict[str, str]
      entry = ...  # type: str
    """)

  def testDictInit(self):
    ty = self.Infer("""
      def f():
        return dict([])
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> Dict[nothing, nothing]
    """)

  def testDictTupleInit(self):
    ty = self.Infer("""
      def f():
        return dict([("foo", "foo")])
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> Dict[str, str]
    """)

  def testEmptyTupleAsArg(self):
    ty = self.Infer("""
      def f(x):
        if x:
          return isinstance(1, ())
        else:
          return 3j
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> bool or complex
    """)

  def testEmptyTypeParamAsArg(self):
    ty = self.Infer("""
      def f():
        return u"".join(map(unicode, ()))
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> unicode
    """)

  def testAccessEmptyDictInIf(self):
    ty = self.Infer("""
      class Foo(object):
        pass

      def f(key):
        d = {}
        if key is None:
          e = Foo()
        else:
          e = d[key]
        e.next = None
        return e
    """, deep=True, solve_unknowns=False, extract_locals=True,
                    report_errors=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        next = ...  # type: NoneType

      def f(key) -> Any
    """)

  def testCascade(self):
    ty = self.Infer("""
      if __any_object__:
        x = 3
      else:
        x = 3.14
      y = divmod(x, x)
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: float or int
      y = ...  # type: Tuple[float or int, ...]
    """)

  def testMaybeAny(self):
    ty = self.Infer("""
      x = __any_object__
      x.as_integer_ratio()
      if x:
        x = 1
      y = divmod(x, 3.14)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: float or int
      y = ...  # type: Tuple[complex or float, ...]
    """)

  def testIndex(self):
    ty = self.Infer("""
      def f():
        l = [__any_object__]
        if __random__:
          pos = None
        else:
          pos = 0
        l[pos] += 1
        return l
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      # The element types aren't more precise since the solver doesn't know
      # which element of the list gets modified.
      def f() -> list
    """)

  def testCircularReferenceList(self):
    ty = self.Infer("""
      def f():
        lst = []
        lst.append(lst)
        return lst
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> List[list]: ...
    """)

  def testCircularReferenceDictionary(self):
    ty = self.Infer("""
      def f():
        g = __any_object__
        s = {}
        if g:
          s1 = {}
          s[__any_object__] = s1
          s = s1
        g = s.get('$end', None)
        s['$end'] = g
        return s1
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> Dict[str, Union[None, dict]]: ...
    """)

  def testEqOperatorOnItemFromEmptyDict(self):
    _, errorlog = self.InferAndCheck("""
      d = {}
      d[1] == d[1]
    """)
    self.assertErrorLogContains(errorlog,
                                r".*item out of dict.*\[index-error\]")
    self.assertEquals(1, len(list(errorlog.unique_sorted_errors())))


if __name__ == "__main__":
  test_inference.main()
