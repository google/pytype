"""Test list, dict, etc."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ContainerTest(test_base.BaseTest):
  """Tests for containers."""

  def test_tuple_pass_through(self):
    self.Check("""
      from typing import Tuple
      def f(x):
        return x
      assert_type(f((3, "str")), Tuple[int, str])
    """)

  def test_tuple(self):
    self.Check("""
      def f(x):
        return x[0]
      assert_type(f((3, "str")), int)
    """)

  def test_tuple_swap(self):
    self.Check("""
      from typing import Tuple
      def f(x):
        return (x[1], x[0])
      assert_type(f((3, "str")), Tuple[str, int])
    """)

  def test_empty_tuple(self):
    ty = self.Infer("""
      def f():
        return ()
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> tuple[()]: ...")

  def test_sets_sanity(self):
    ty = self.Infer("""
      def f():
        x = set([1])
        x.add(10)
        return x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> set[int]: ...")

  def test_sets_add(self):
    ty = self.Infer("""
      def f():
        x = set([])
        x.add(1)
        x.add(10)
        return x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> set[int]: ...")

  def test_sets(self):
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
    """)
    self.assertTypesMatchPytd(ty, "def f() -> set[int]: ...")

  def test_list_literal(self):
    ty = self.Infer("""
      def f():
        return [1, 2, 3]
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int]: ...")

  def test_list_append(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int]: ...")

  def test_list_setitem(self):
    ty = self.Infer("""
      layers = [((),)]
      for x, in layers:
        layers[0] = x,
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, Tuple
      layers = ...  # type: List[Tuple[Tuple[()]]]
      x = ...  # type: Tuple[()]
    """,
    )

  def test_list_concat(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return [0] + x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int]: ...")

  def test_list_concat_multi_type(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append("str")
        return x + [1.3] + x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int | float | str]: ...")

  def test_union_into_type_param(self):
    ty = self.Infer("""
      y = __any_object__
      if y:
        x = 3
      else:
        x = 3.1
      l = []
      l.append(x)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, List, Union
      x = ...  # type: Union[int, float]
      y = ...  # type: Any
      l = ...  # type: List[Union[int, float]]
    """,
    )

  def test_list_concat_unlike(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return ["str"] + x
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int | str]: ...")

  def test_any_object(self):
    ty = self.Infer("""
      def f():
        return __any_object__
      def g():
        return __any_object__()
      def h():
        return __any_object__("name")
      f(); g(); h()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def f() -> Any: ...
      def g() -> Any: ...
      def h() -> Any: ...
    """,
    )

  def test_dict_literal(self):
    ty = self.Infer("""
      def f():
        return {"test": 1, "arg": 42}
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> dict[str, int]: ...")

  def test_dict_empty_constructor(self):
    ty = self.Infer("""
      def f():
        return dict()
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> dict[nothing, nothing]: ...")

  def test_dict_constructor(self):
    ty = self.Infer("""
      def f():
        return dict([(1, 2), (3, 4)])
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> dict[int, int]: ...")

  def test_dict_constructor2(self):
    ty = self.Infer("""
      def f():
        return dict([(1, "bar"), (2, "foo")])
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> dict[int, str]: ...")

  def test_dict_setitem(self):
    ty = self.Infer("""
      def f():
        d = {}
        d["test"] = 1
        d["arg"] = 42
        return d
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> dict[str, int]: ...")

  def test_dict_update(self):
    ty = self.Infer("""
      d = {}
      d.update({"a": 1}, b=2j)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, Union
      d = ...  # type: Dict[str, Union[int, complex]]
    """,
    )

  def test_ambiguous_dict_update(self):
    ty = self.Infer("""
      d = {}
      d.update({"a": 1} if __random__ else {"b": 2j}, c=3.0)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict, Union
      d = ...  # type: Dict[str, Union[int, float, complex]]
    """,
    )

  def test_for_iter(self):
    ty = self.Infer("""
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class A:
        parent: int | str
        def __init__(self) -> None: ...
      def set_parent(l) -> None: ...
      def f() -> int | str: ...
    """,
    )

  def test_overloading(self):
    ty = self.Infer("""
      class Base:
        parent = None
        children = ()
        def bar(self, new):
          if self.parent:
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Base:
        parent: None
        children: tuple[()]
        def bar(self, new) -> None: ...
      class Node(Base):
        children: list
        def __init__(self, children) -> None: ...
      class Leaf(Base):
        parent: Node
        foobar: int
        def __init__(self) -> None: ...
      def f() -> int: ...
    """,
    )

  def test_class_attr(self):
    ty = self.Infer("""
      class Node:
        children = ()

      def f():
        n1 = Node()
        n1.children = [n1]
        for ch in n1.children:
          ch.foobar = 3
        return n1.foobar

      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Node:
        children: tuple[()] | list[Node]
        foobar: int
      def f() -> int: ...
    """,
    )

  def test_heterogeneous(self):
    ty = self.Infer("""
      def f():
        x = list()
        x.append(3)
        x.append("str")
        return x[0]
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int | str: ...")

  def test_list_comprehension(self):
    # uses byte_LIST_APPEND
    ty = self.Infer("""
      def f():
        return [i for i in (1,2,3)]
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> list[int]: ...")

  def test_set_comprehension(self):
    # uses byte_SET_ADD
    ty = self.Infer("""
      def f():
        return {i for i in [1,2,3]}
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> set[int]: ...")

  def test_empty_or_string(self):
    ty = self.Infer("""
      d = dict()
      d["a"] = "queen"
      entry = d["a"]
      open('%s' % entry, 'w')
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict
      d = ...  # type: Dict[str, str]
      entry = ...  # type: str
    """,
    )

  def test_dict_init(self):
    ty = self.Infer("""
      def f():
        return dict([])
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict
      def f() -> Dict[nothing, nothing]: ...
    """,
    )

  def test_dict_tuple_init(self):
    ty = self.Infer("""
      def f():
        return dict([("foo", "foo")])
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict
      def f() -> Dict[str, str]: ...
    """,
    )

  def test_empty_tuple_as_arg(self):
    ty = self.Infer("""
      def f(x):
        if x:
          return isinstance(1, ())
        else:
          return 3j
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Union
      def f(x) -> Union[bool, complex]: ...
    """,
    )

  def test_empty_type_param_as_arg(self):
    ty = self.Infer("""
      def f():
        return sum(map(int, ()))
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def f() -> Any: ...
    """,
    )

  def test_access_empty_dict_in_if(self):
    ty = self.Infer(
        """
      class Foo:
        pass

      def f(key):
        d = {}
        if key is None:
          e = Foo()
        else:
          e = d[key]
        e.next = None
        return e
    """,
        report_errors=False,
    )
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo:
        next = ...  # type: NoneType

      def f(key) -> Foo: ...
    """,
    )

  def test_cascade(self):
    ty = self.Infer("""
      if __random__:
        x = 3
      else:
        x = 3.14
      y = divmod(x, x)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Tuple, Union
      x = ...  # type: Union[float, int]
      y = ...  # type: Tuple[Union[float, int], Union[float, int]]
    """,
    )

  def test_maybe_any(self):
    ty = self.Infer("""
      x = __any_object__
      x.as_integer_ratio()
      if x:
        x = 1
      y = divmod(x, 3.14)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Tuple
      x = ...  # type: Any
      y = ...  # type: Tuple[Any, Any]
    """,
    )

  def test_index(self):
    ty = self.Infer("""
      def f():
        l = [__any_object__]
        if __random__:
          pos = __any_object__
        else:
          pos = 0
        l[pos] += 1
        return l
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      # The element types aren't more precise since the solver doesn't know
      # which element of the list gets modified.
      def f() -> list: ...
    """,
    )

  def test_circular_reference_list(self):
    ty = self.Infer("""
      def f():
        lst = []
        lst.append(lst)
        return lst
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      def f() -> List[list]: ...
    """,
    )

  def test_circular_reference_dictionary(self):
    ty = self.Infer("""
      def f():
        g = __any_object__
        s = {}
        s1 = {}
        if g:
          s1 = {}
          s[__any_object__] = s1
          s = s1
        g = s.get('$end', None)
        s['$end'] = g
        return s1
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, Union
      # TODO(b/159069936): This should be "Dict[str, none]". s1 above can never
      # contain another dictionary.
      def f() -> Dict[str, Union[None, dict]]: ...
    """,
    )

  def test_eq_operator_on_item_from_empty_dict(self):
    self.Check("""
      d = {}
      d[1] == d[1]
    """)

  def test_dict(self):
    ty = self.Infer("""
      mymap = {'a': 3.14, 'b':1}
      a = mymap['a']
      b1 = mymap['b']
      c = mymap['foobar']  # unrecognized values are treated as Any
      mymap[str()] = 3j
      b2 = mymap['b']
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict, Union
      mymap = ...  # type: Dict[str, Union[int, float, complex]]
      a = ...  # type: float
      b1 = ...  # type: int
      c = ...  # type: Any
      b2 = ...  # type: Union[int, float, complex]
    """,
    )

  def test_dict_or_any(self):
    self.Check("""
      if __random__:
        results = __any_object__
      else:
        results = {}
      if "foo" in results:
        results["foo"]
    """)

  def test_dict_getitem(self):
    ty = self.Infer("""
      v = {}
      a = v.__getitem__("a")
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict
      v: Dict[nothing, nothing]
      a: Any
    """,
    )

  def test_empty_list(self):
    ty = self.Infer("""
      cache = {
        "data": {},
        "lru": [],
      }
      def read(path):
        if path:
          cache["lru"].append(path)
        else:
          oldest = cache["lru"].pop(0)
          return oldest
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict, Union
      cache = ...  # type: Dict[str, Union[Dict[nothing, nothing], list]]
      def read(path) -> None: ...
    """,
    )

  def test_recursive_definition_and_conflict(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Generic[T]): ...
        class Baz(Foo[Baz], Bar[str]): ...
      """,
      )
      self.Check(
          """
        import foo
        foo.Baz()
      """,
          pythonpath=[d.path],
      )

  def test_foo(self):
    _ = self.Infer("""
      import collections
      class A(collections.namedtuple("_", ["a"])):
        pass
      class B(A, dict):
        pass
    """)

  def test_constructor_empty(self):
    ty = self.Infer("""
      empty = []
      y = [list(x) for x in empty]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      empty = ...  # type: List[nothing]
      y = ...  # type: List[List[nothing]]
    """,
    )


if __name__ == "__main__":
  test_base.main()
