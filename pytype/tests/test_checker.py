"""Tests for --check."""

import textwrap

from pytype import analyze
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype.tests import test_base


class CheckerTest(test_base.BaseTest):
  """Tests for --check."""

  def get_checking_errors(self, python):
    options = config.Options.create(python_version=self.PYTHON_VERSION,
                                    python_exe=self.PYTHON_EXE)
    errorlog = errors.ErrorLog()
    loader = load_pytd.Loader(self.options.module_name, self.options)
    analyze.check_types(py_src=textwrap.dedent(python),
                        loader=loader,
                        py_filename="<inline>",
                        errorlog=errorlog,
                        options=options)
    return errorlog

  def testSet(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import List, Set
      def f(data: List[str]):
        data = set(x for x in data)
        g(data)
      def g(data: Set[str]):
        pass
    """)

  def testRecursiveForwardReference(self):
    python = """\
      from __future__ import google_type_annotations
      class X(object):
        def __init__(self, val: "X"):
          pass
      def f():
        X(42)
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(6, "wrong-arg-types", r"X.*int")])

  def testBadReturnTypeInline(self):
    python = """\
      from __future__ import google_type_annotations
      from typing import List
      def f() -> List[int]:
        return [object()]
      f()[0] += 1
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"List\[int\].*List\[object\]")])

  def testUseVarargsAndKwargs(self):
    self.Check("""\
      from __future__ import google_type_annotations
      class A(object):
        pass
      def f(*args: A, **kwargs: A):
        for arg in args:
          pass
        for kwarg in kwargs:
          pass
    """)

  def testNestedNoneType(self):
    self.Check("""\
      from __future__ import google_type_annotations
      from typing import List, Union
      def f1() -> Union[None]:
        pass
      def f2() -> List[None]:
        return [None]
      def g1(x: Union[None]):
        pass
      def g2(x: List[None]):
        pass
    """)

  def testInnerClassInit(self):
    self.Check("""\
      from __future__ import google_type_annotations
      from typing import List
      class A:
        def __init__(self):
          self.x = 42
      def f(v: List[A]):
        return v[0].x
      def g() -> List[A]:
        return [A()]
      def h():
        return g()[0].x
    """)

  def testRecursion(self):
    self.Check("""\
      from __future__ import google_type_annotations
      class A:
        def __init__(self, x: "B"):
          pass
      class B:
        def __init__(self):
          self.x = 42
          self.y = A(self)
    """)

  def testBadDictValue(self):
    python = """\
      from __future__ import google_type_annotations
      from typing import Dict
      def f() -> Dict[str, int]:
        return {"x": 42.0}
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type", r"int.*float")])

  def testInstanceAsAnnotation(self):
    python = """\
      from __future__ import google_type_annotations
      def f():
        pass
      def g(x: f):
        pass
      def h(x: 3):
        pass
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "invalid-annotation",
                                      r"instance of Callable.*x"),
                                     (6, "invalid-annotation",
                                      r"3.*x")])

  def testBadGenerator(self):
    python = """\
      from __future__ import google_type_annotations
      from typing import Generator
      def f() -> Generator[str]:
        for i in range(3):
          yield i
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(5, "bad-return-type",
                                      r"Generator\[str, Any, Any\].*"
                                      r"Generator\[int, Any, Any\]")])

  def testMultipleParameterBindings(self):
    python = """\
      from __future__ import google_type_annotations
      from typing import List
      def f(x) -> List[int]:
        return ["", x]
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"List\[int\].*List\[str\]")])

  def testNoParamBinding(self):
    python = """\
      from __future__ import google_type_annotations
      def f() -> None:
        x = []
        return x
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"None.*List\[nothing\]")])

  def testAttributeInIncompleteInstance(self):
    python = """\
      from __future__ import google_type_annotations
      from typing import List
      class Foo(object):
        def __init__(self, other: "List[Foo]"):
          self.x = other[0].x  # okay
          self.y = other.y  # No "y" on List[Foo]
          self.z = Foo.z  # No "z" on Type[Foo]
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(6, "attribute-error", r"y.*List\[Foo\]"),
                                     (7, "attribute-error", r"z.*Type\[Foo\]")])

  def testBadGetItem(self):
    python = """\
      from __future__ import google_type_annotations
      def f(x: int):
        return x[0]
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(3, "unsupported-operands", r"int.*int")])

  def testBadAnnotationContainer(self):
    python = """\
      from __future__ import google_type_annotations
      class A(object):
        pass
      def f(x: int[str]):
        pass
      def g(x: A[str]):
        pass
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(4, "not-indexable", r"Generic"),
                                     (6, "not-indexable", r"Generic")])


if __name__ == "__main__":
  test_base.main()
