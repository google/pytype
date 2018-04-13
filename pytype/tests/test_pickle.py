"""Tests for loading and saving pickled files."""


from pytype import load_pytd
from pytype import utils
from pytype.pytd import visitors
from pytype.tests import test_base
from six.moves import cPickle


class PickleTest(test_base.BaseTest):
  """Tests for loading and saving pickled files."""

  def _verifyDeps(self, module, immediate_deps, late_deps):
    if isinstance(module, bytes):
      data = cPickle.loads(module)
      self.assertItemsEqual(data.dependencies, immediate_deps)
      ast = data.ast
    else:
      c = visitors.CollectDependencies()
      module.Visit(c)
      self.assertItemsEqual(c.modules, immediate_deps)
      ast = module
    c = visitors.CollectLateDependencies()
    ast.Visit(c)
    self.assertItemsEqual(c.modules, late_deps)

  def testContainer(self):
    pickled = self.Infer("""
      from __future__ import google_type_annotations
      import collections, json
      def f() -> collections.OrderedDict[int, int]:
        return collections.OrderedDict({1: 1})
      def g() -> json.JSONDecoder:
        return json.JSONDecoder()
    """, pickle=True, module_name="foo")
    with utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.f()
      """, deep=False, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        import collections
        u = ...  # type: module
        r = ...  # type: collections.OrderedDict[int, int]
      """)

  def testType(self):
    pickled = self.Infer("""
      x = type
    """, deep=False, pickle=True, module_name="foo")
    with utils.Tempdir() as d:
      u = d.create_file("u.pickled", pickled)
      ty = self.Infer("""
        import u
        r = u.x
      """, deep=False, pythonpath=[""], imports_map={"u": u})
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import collections
        u = ...  # type: module
        r = ...  # type: Type[type]
      """)

  def testCopyClassIntoOutput(self):
    pickled_foo = self.Infer("""
      import asyncore
      a = 42
      file_dispatcher = asyncore.file_dispatcher  # copy class
    """, deep=False, pickle=True, module_name="foo")
    self._verifyDeps(pickled_foo, ["__builtin__"], ["asyncore"])
    with utils.Tempdir() as d:
      foo = d.create_file("foo.pickled", pickled_foo)
      pickled_bar = self.Infer("""
        import foo
        file_dispatcher = foo.file_dispatcher  # copy class
      """, pickle=True, pythonpath=[""],
                               imports_map={"foo": foo}, module_name="bar")
      self._verifyDeps(pickled_bar, ["__builtin__"], ["asyncore"])
      bar = d.create_file("bar.pickled", pickled_bar)
      ty = self.Infer("""
        import bar
        r = bar.file_dispatcher(0)
      """, deep=False, pythonpath=[""], imports_map={"foo": foo, "bar": bar})
      self._verifyDeps(ty, ["asyncore", "__builtin__"], [])
      self.assertTypesMatchPytd(ty, """
        import asyncore
        bar = ...  # type: module
        r = ...  # type: asyncore.file_dispatcher
      """)

  def testOptimizeOnLateTypes(self):
    with utils.Tempdir() as d:
      pickled_foo = self.Infer("""
        class X(object): pass
      """, deep=False, pickle=True, module_name="foo")
      self._verifyDeps(pickled_foo, ["__builtin__"], [])
      foo = d.create_file("foo.pickled", pickled_foo)
      pickled_bar = self.Infer("""
        import foo
        def f():
          return foo.X()
      """, pickle=True, pythonpath=[""],
                               imports_map={"foo": foo}, module_name="bar",
                               deep=True)
      bar = d.create_file("bar.pickled", pickled_bar)
      self._verifyDeps(pickled_bar, ["__builtin__"], ["foo"])
      self.Infer("""
        import bar
        f = bar.f
      """, deep=False, imports_map={"foo": foo, "bar": bar})

  def testFileChange(self):
    with utils.Tempdir() as d:
      pickled_xy = self.Infer("""
        class X(object): pass
        class Y(object): pass
      """, deep=False, pickle=True, module_name="foo")
      pickled_x = self.Infer("""
        class X(object): pass
      """, deep=False, pickle=True, module_name="foo")
      foo = d.create_file("foo.pickled", pickled_xy)
      pickled_bar = self.Infer("""
        import foo
        class A(foo.X): pass
        class B(foo.Y): pass
      """, deep=False, pickle=True, imports_map={"foo": foo}, module_name="bar")
      self._verifyDeps(pickled_bar, ["__builtin__"], ["foo"])
      bar = d.create_file("bar.pickled", pickled_bar)
      # Now, replace the old foo.pickled with a version that doesn't have Y
      # anymore.
      foo = d.create_file("foo.pickled", pickled_x)
      self.Infer("""
        import bar
        a = bar.A()
        b = bar.B()
      """, deep=False, imports_map={"foo": foo, "bar": bar})
      # Also try deleting the file.
      d.delete_file("foo.pickled")
      self.Infer("""
        import bar
        a = bar.A()
        b = bar.B()
      """, deep=False, imports_map={"foo": foo, "bar": bar})

  def testFileRename(self):
    with utils.Tempdir() as d:
      pickled_other_foo = self.Infer("""
        class Foo: pass
      """, deep=False, pickle=True, module_name="bar")
      other_foo = d.create_file("empty.pickled", pickled_other_foo)
      pickled_foo = self.Infer("""
        class Foo:
          def __init__(self): pass
        x = Foo()
      """, deep=False, pickle=True, module_name="foo")
      foo = d.create_file("foo.pickled", pickled_foo)
      self.Infer("""
        import bar
        bar.Foo()
      """, pickle=True,
                 imports_map={"bar": foo,  # rename to "bar"
                              "foo": other_foo},
                 module_name="baz")

  def testOptimize(self):
    with utils.Tempdir() as d:
      pickled_foo = self.PicklePyi("""
        import UserDict
        class Foo(object): ...
        @overload
        def f(self, x: Foo, y: UserDict.UserDict): ...
        @overload
        def f(self, x: UserDict.UserDict, y: Foo): ...
      """, module_name="foo")
      self._verifyDeps(pickled_foo, ["__builtin__", "foo"], ["UserDict"])
      foo = d.create_file("foo.pickled", pickled_foo)
      self.assertNoCrash(self.Infer, """
        from __future__ import google_type_annotations
        import foo
        class Bar(object):
          f = foo.f
      """, imports_map={"foo": foo}, module_name="bar")

  def testFunctionType(self):
    self.loader = load_pytd.PickledPyiLoader(
        base_module="bar",
        python_version=self.PYTHON_VERSION,
        pythonpath=[""])
    with utils.Tempdir() as d:
      pickled_foo = self.PicklePyi("""
        import UserDict
        def f(x: UserDict.UserDict) -> None: ...
      """, module_name="foo")
      foo = d.create_file("foo.pickled", pickled_foo)
      self.loader.imports_map = {"foo": foo}
      pickled_bar = self.PicklePyi("""
        from foo import f  # Alias(name="f", type=FunctionType("foo.f", f))
      """, module_name="bar")
      bar = d.create_file("bar.pickled", pickled_bar)
      self.assertNoCrash(self.Infer, """
        from __future__ import google_type_annotations
        import bar
        bar.f(42)
      """, imports_map={"foo": foo, "bar": bar}, module_name="baz")


if __name__ == "__main__":
  test_base.main()
