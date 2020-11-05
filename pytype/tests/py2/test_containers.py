"""Test list, dict, etc."""

from pytype import file_utils
from pytype.tests import test_base


class ContainerTest(test_base.TargetPython27FeatureTest):
  """Tests for containers."""

  # A lot of these tests depend on comprehensions like [x for x in ...] binding
  # x in the outer scope, which does not happen in python3.
  #
  # TODO(rechen): Write python3 versions of these.

  def test_iterate_pyi_list_nothing(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List
        lst1 = ...  # type: List[nothing]
      """)
      ty = self.Infer("""
        import a
        lst2 = [x for x in a.lst1]
        x.some_attribute = 42
        y = x.some_attribute
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, List
        a = ...  # type: module
        lst2 = ...  # type: List[nothing]
        x = ...  # type: Any
        y = ...  # type: Any
      """)

  def test_iterate_pyi_list_any(self):
    # Depends on [x for x in ...] binding x in the outer scope
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, List
        lst1 = ...  # type: List[Any]
      """)
      ty = self.Infer("""
        import a
        lst2 = [x for x in a.lst1]
        x.some_attribute = 42
        y = x.some_attribute
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        lst2 = ...  # type: list
        x = ...  # type: Any
        y = ...  # type: Any
      """)

  def test_leaking_type(self):
    ty = self.Infer("""
      import sys
      a = [str(ty) for ty in (float, int, bool)[:len(sys.argv)]]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Type, Union
      sys = ...  # type: module
      a = ...  # type: List[str, ...]
      ty = ...  # type: Type[Union[float, int]]
    """)

  def test_call_empty(self):
    ty = self.Infer("""
      empty = []
      y = [x() for x in empty]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      empty = ...  # type: List[nothing]
      y = ...  # type: List[nothing]
      x = ...  # type: Any
    """)

  def test_iterate_pyi_list_union(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, Set, Union
        lst1 = ...  # type: Union[List[nothing], Set[int]]
      """)
      ty = self.Infer("""
        import a
        lst2 = [x for x in a.lst1]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        a = ...  # type: module
        lst2 = ...  # type: List[int]
        x = ...  # type: int
      """)

  def test_iterate_pyi_list(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        lst1 = ...  # type: list
      """)
      ty = self.Infer("""
        import a
        lst2 = [x for x in a.lst1]
        x.some_attribute = 42
        y = x.some_attribute
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        lst2 = ...  # type: list
        x = ...  # type: Any
        y = ...  # type: Any
      """)

  def test_iterate_pyi_list_int(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List
        lst1 = ...  # type: List[int]
      """)
      ty = self.Infer("""
        import a
        lst2 = [x for x in a.lst1]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        a = ...  # type: module
        lst2 = ...  # type: List[int]
        x = ...  # type: int
      """)

  def test_isinstance_empty(self):
    ty = self.Infer("""
      empty = []
      y = [isinstance(x, int) for x in empty]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      empty = ...  # type: List[nothing]
      y = ...  # type: List[bool]
      x = ...  # type: Any
    """)

  def test_inner_class_empty(self):
    ty = self.Infer("""
      empty = []
      def f(x):
        class X(x):
          pass
        return {X: X()}
      y = [f(x) for x in empty]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, List
      empty = ...  # type: List[nothing]
      def f(x) -> Dict[type, Any]: ...
      y = ...  # type: List[Dict[type, Any]]
      x = ...  # type: Any
    """)

  def test_iterate_empty_list(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      x.some_attribute = 42
      y = x.some_attribute
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      x = ...  # type: Any
      y = ...  # type: Any
    """)

  def test_branch_empty(self):
    ty = self.Infer("""
      empty = []
      def f(x):
        if x:
          return 3
        else:
          return "foo"
      y = [f(x) for x in empty]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Union
      empty = ...  # type: List[nothing]
      def f(x) -> Union[int, str]: ...
      y = ...  # type: List[Union[int, str]]
      x = ...  # type: Any
    """)

  def test_dict_comprehension(self):
    # uses byte_MAP_ADD
    ty = self.Infer("""
      def f():
        return {i: i for i in xrange(3)}
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_int_dict))

  def test_constructor_empty(self):
    ty = self.Infer("""
      empty = []
      y = [list(x) for x in empty]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      empty = ...  # type: List[nothing]
      y = ...  # type: List[List[nothing]]
      x = ...  # type: Any
    """)

  # Uses unicode
  def test_empty_type_param_as_arg(self):
    ty = self.Infer("""
      def f():
        return u"".join(map(unicode, ()))
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> unicode: ...
    """)


test_base.main(globals(), __name__ == "__main__")
