"""Tests for loading and saving pickled files."""

import textwrap

from pytype import file_utils
from pytype.pyi import parser
from pytype.pytd import visitors
from pytype.tests import test_base

import six
from six.moves import cPickle


class PickleTest(test_base.TargetIndependentTest):
  """Tests for loading and saving pickled files."""

  def PicklePyi(self, src, module_name):
    src = textwrap.dedent(src)
    ast = parser.parse_string(src, python_version=self.python_version)
    ast = ast.Visit(visitors.LookupBuiltins(
        self.loader.builtins, full_names=False))
    return self._Pickle(ast, module_name)

  def _verifyDeps(self, module, immediate_deps, late_deps):
    if isinstance(module, bytes):
      data = cPickle.loads(module)
      six.assertCountEqual(self, dict(data.dependencies), immediate_deps)
      six.assertCountEqual(self, dict(data.late_dependencies), late_deps)
    else:
      c = visitors.CollectDependencies()
      module.Visit(c)
      six.assertCountEqual(self, c.dependencies, immediate_deps)
      six.assertCountEqual(self, c.late_dependencies, late_deps)

  def test_type(self):
    pickled = self.Infer("""
      x = type
    """, deep=False, pickle=True, module_name="foo")
    with file_utils.Tempdir() as d:
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

  def test_copy_class_into_output(self):
    pickled_foo = self.Infer("""
      import asyncore
      a = 42
      file_dispatcher = asyncore.file_dispatcher  # copy class
    """, deep=False, pickle=True, module_name="foo")
    self._verifyDeps(pickled_foo, ["__builtin__"], ["asyncore"])
    with file_utils.Tempdir() as d:
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

  def test_optimize_on_late_types(self):
    with file_utils.Tempdir() as d:
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

  def test_file_change(self):
    with file_utils.Tempdir() as d:
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

  def test_file_rename(self):
    with file_utils.Tempdir() as d:
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

  def test_optimize(self):
    with file_utils.Tempdir() as d:
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
        import foo
        class Bar(object):
          f = foo.f
      """, imports_map={"foo": foo}, module_name="bar")

  def test_function_type(self):
    self.ConfigureOptions(
        module_name="bar",
        pythonpath=[""],
        use_pickled_files=True)
    pickled_foo = self.PicklePyi("""
        import UserDict
        def f(x: UserDict.UserDict) -> None: ...
      """, module_name="foo")
    with file_utils.Tempdir() as d:
      foo = d.create_file("foo.pickled", pickled_foo)
      self.loader.imports_map = {"foo": foo}
      pickled_bar = self.PicklePyi("""
        from foo import f  # Alias(name="f", type=FunctionType("foo.f", f))
      """, module_name="bar")
      bar = d.create_file("bar.pickled", pickled_bar)
      self.assertNoCrash(self.Infer, """
        import bar
        bar.f(42)
      """, imports_map={"foo": foo, "bar": bar}, module_name="baz")


test_base.main(globals(), __name__ == "__main__")
