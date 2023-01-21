"""Tests for import."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ImportTest(test_base.BaseTest):
  """Tests for import."""

  def test_module_attributes(self):
    ty = self.Infer("""
      import os
      f = os.__file__
      n = os.__name__
      d = os.__doc__
      p = os.__package__
      """)
    self.assertTypesMatchPytd(ty, """
       import os
       from typing import Optional
       f = ...  # type: str
       n = ...  # type: str
       d = ...  # type: str
       p = ...  # type: Optional[str]
    """)

  def test_import_sys2(self):
    ty = self.Infer("""
      import sys
      import bad_import  # doesn't exist
      def f():
        return sys.stderr
      def g():
        return sys.maxsize
      def h():
        return sys.getrecursionlimit()
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      import sys
      from typing import Any, TextIO
      bad_import = ...  # type: Any
      def f() -> TextIO: ...
      def g() -> int: ...
      def h() -> int: ...
    """)

  def test_relative_priority(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", "x = ...  # type: int")
      d.create_file("b/a.pyi", "x = ...  # type: complex")
      ty = self.Infer("""
        import a
        x = a.x
      """, deep=False, pythonpath=[d.path], module_name="b.main")
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: int
      """)

  def test_import_attribute_error(self):
    self.CheckWithErrors("""
      try:
        import nonexistent  # import-error
      except ImportError as err:
        print(err.name)
    """)

  def test_datetime_datetime(self):
    with self.DepTree([("foo.py", "from datetime import datetime")]):
      self.Check("""
        import foo
        assert_type(foo.datetime(1, 1, 1), "datetime.datetime")
      """)

  def test_cycle(self):
    # See https://github.com/google/pytype/issues/1028. This can happen when a
    # file needs to be analyzed twice due to a dependency cycle.
    with self.DepTree([("components.pyi", """
      import loaders
      from typing import Dict, Type
      Foo: Type[loaders.Foo]
      class Component:
        def __init__(self, foos: Dict[int, loaders.Foo]) -> None: ...
    """), ("loaders.pyi", """
      from typing import Any, NamedTuple
      Component: Any
      class Foo(NamedTuple):
        foo: int
      def load() -> Any: ...
    """)]):
      self.Infer("""
        from typing import Dict, NamedTuple
        from components import Component
        class Foo(NamedTuple):
          foo: int
        def load() -> Component:
          foos: Dict[int, Foo] = {}
          return Component(foos=foos)
      """, module_name="loaders")


if __name__ == "__main__":
  test_base.main()
