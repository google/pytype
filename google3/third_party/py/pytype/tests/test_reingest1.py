"""Tests for reloading generated pyi."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class ReingestTest(test_base.BaseTest):
  """Tests for reloading the pyi we generate."""

  def test_container(self):
    ty = self.Infer("""
      class Container:
        def Add(self):
          pass
      class A(Container):
        pass
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      self.Check("""
        # u.py
        from foo import A
        A().Add()
      """, pythonpath=[d.path])

  def test_union(self):
    ty = self.Infer("""
      class Union:
        pass
      x = {"Union": Union}
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      self.Check("""
        from foo import Union
      """, pythonpath=[d.path])

  def test_identity_decorators(self):
    foo = self.Infer("""
      def decorate(f):
        return f
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        @foo.decorate
        def f():
          return 3
        def g():
          return f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        def f() -> int: ...
        def g() -> int: ...
      """)

  @test_base.skip("Needs better handling of Union[Callable, f] in output.py.")
  def test_maybe_identity_decorators(self):
    foo = self.Infer("""
      def maybe_decorate(f):
        return f or (lambda *args: 42)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        @foo.maybe_decorate
        def f():
          return 3
        def g():
          return f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        def f() -> int: ...
        def g() -> int: ...
      """)

  def test_namedtuple(self):
    foo = self.Infer("""
      import collections
      X = collections.namedtuple("X", ["a", "b"])
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        foo.X(0, 0)
        foo.X(a=0, b=0)
      """, pythonpath=[d.path])

  def test_new_chain(self):
    foo = self.Infer("""
      class X:
        def __new__(cls, x):
          return super(X, cls).__new__(cls)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        class Y(foo.X):
          def __new__(cls, x):
            return super(Y, cls).__new__(cls, x)
          def __init__(self, x):
            self.x = x
        Y("x").x
      """, pythonpath=[d.path])

  def test_namedtuple_subclass(self):
    foo = self.Infer("""
      import collections
      class X(collections.namedtuple("X", ["a"])):
        def __new__(cls, a, b):
          _ = b
          return super(X, cls).__new__(cls, a)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      _, errors = self.InferWithErrors("""
        import foo
        foo.X("hello", "world")
        foo.X(42)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"b.*__new__"})

  def test_alias(self):
    foo = self.Infer("""
      class _Foo:
        def __new__(cls, _):
          return super(_Foo, cls).__new__(cls)
      Foo = _Foo
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        foo.Foo("hello world")
      """, pythonpath=[d.path])

  def test_dynamic_attributes(self):
    foo1 = self.Infer("""
      HAS_DYNAMIC_ATTRIBUTES = True
    """)
    foo2 = self.Infer("""
      has_dynamic_attributes = True
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo1.pyi", pytd_utils.Print(foo1))
      d.create_file("foo2.pyi", pytd_utils.Print(foo2))
      d.create_file("bar.pyi", """
        from foo1 import xyz
        from foo2 import zyx
      """)
      self.Check("""
        import foo1
        import foo2
        import bar
        foo1.abc
        foo2.abc
        bar.xyz
        bar.zyx
      """, pythonpath=[d.path])

  def test_inherited_mutation(self):
    foo = self.Infer("""
      class MyList(list):
        write = list.append
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        lst = foo.MyList()
        lst.write(42)
      """, pythonpath=[d.path])
      # MyList is not parameterized because it inherits from List[Any].
      self.assertTypesMatchPytd(ty, """
        import foo
        lst = ...  # type: foo.MyList
      """)

  @test_base.skip("Need to give MyList.write the right self mutation.")
  def test_inherited_mutation_in_generic_class(self):
    foo = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar("T")
      class MyList(List[T]):
        write = list.append
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        lst = foo.MyList()
        lst.write(42)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        lst = ...  # type: foo.MyList[int]
      """)

  def test_instantiate_imported_generic(self):
    foo = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self):
          pass
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        x = foo.Foo[int]()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x: foo.Foo[int]
      """)


class StrictNoneTest(test_base.BaseTest):
  """Tests for strict none."""

  def setUp(self):
    super().setUp()
    self.options.tweak(strict_none_binding=False)

  def test_pyi_return_constant(self):
    foo = self.Infer("""
      x = None
      def f():
        return x
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        def g():
          return foo.f().upper()
      """, pythonpath=[d.path])

  def test_pyi_yield_constant(self):
    foo = self.Infer("""
      x = None
      def f():
        yield x
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        def g():
          return [v.upper() for v in foo.f()]
      """, pythonpath=[d.path])

  def test_pyi_return_contained_constant(self):
    foo = self.Infer("""
      x = None
      def f():
        return [x]
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        def g():
          return [v.upper() for v in foo.f()]
      """, pythonpath=[d.path])

  def test_pyi_return_attribute(self):
    foo = self.Infer("""
      class Foo:
        x = None
      def f():
        return Foo.x
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        def g():
          return foo.f().upper()
      """, pythonpath=[d.path])

  def test_no_return(self):
    foo = self.Infer("""
      def fail():
        raise ValueError()
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        def g():
          x = "hello" if __random__ else None
          if x is None:
            foo.fail()
          return x.upper()
      """, pythonpath=[d.path])

  def test_context_manager_subclass(self):
    foo = self.Infer("""
      class Foo:
        def __enter__(self):
          return self
        def __exit__(self, type, value, traceback):
          return None
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        class Bar(foo.Foo):
          x = None
        with Bar() as bar:
          bar.x
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
