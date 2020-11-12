"""Test list, dict, etc."""

from pytype import file_utils
from pytype.pytd import pytd
from pytype.tests import test_base


class ContainerTest(test_base.TargetIndependentTest):
  """Tests for containers."""

  def test_tuple_pass_through(self):
    ty = self.Infer("""
      def f(x):
        return x
      f((3, "str"))
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.TupleType(self.tuple, (self.int, self.str)),),
         pytd.TupleType(self.tuple, (self.int, self.str))))

  def test_tuple(self):
    ty = self.Infer("""
      def f(x):
        return x[0]
      f((3, "str"))
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.TupleType(self.tuple, (self.int, self.str)),),
         self.int))

  def test_tuple_swap(self):
    ty = self.Infer("""
      def f(x):
        return (x[1], x[0])
      f((3, "str"))
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((pytd.TupleType(self.tuple, (self.int, self.str)),),
         pytd.TupleType(self.tuple, (self.str, self.int))))

  def test_empty_tuple(self):
    ty = self.Infer("""
      def f():
        return ()
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.tuple, (pytd.NothingType(),))))

  def test_sets_sanity(self):
    ty = self.Infer("""
      def f():
        x = set([1])
        x.add(10)
        return x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.set, (self.int,))))

  def test_sets_add(self):
    ty = self.Infer("""
      def f():
        x = set([])
        x.add(1)
        x.add(10)
        return x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.set, (self.int,))))

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
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.set, (self.int,))))

  def test_list_literal(self):
    ty = self.Infer("""
      def f():
        return [1, 2, 3]
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.list, (self.int,))))

  def test_list_append(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.list, (self.int,))))

  def test_list_setitem(self):
    ty = self.Infer("""
      layers = [((),)]
      for x, in layers:
        layers[0] = x,
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      layers = ...  # type: List[Tuple[Tuple[()]]]
      x = ...  # type: Tuple[()]
    """)

  def test_list_concat(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return [0] + x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.list, (self.int,))))

  def test_list_concat_multi_type(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append("str")
        return x + [1.3] + x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((),
         pytd.GenericType(
             self.list,
             (pytd.UnionType((self.int, self.float, self.str)),))))

  def test_union_into_type_param(self):
    ty = self.Infer("""
      y = __any_object__
      if y:
        x = 3
      else:
        x = 3.1
      l = []
      l.append(x)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Union
      x = ...  # type: Union[int, float]
      y = ...  # type: Any
      l = ...  # type: List[Union[int, float], ...]
    """)

  def test_list_concat_unlike(self):
    ty = self.Infer("""
      def f():
        x = []
        x.append(1)
        x.append(2)
        x.append(3)
        return ["str"] + x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), pytd.GenericType(self.list, (self.intorstr,))))

  def test_any_object(self):
    ty = self.Infer("""
      def f():
        return __any_object__
      def g():
        return __any_object__()
      def h():
        return __any_object__("name")
      f(); g(); h()
    """, deep=False)
    self.assertHasOnlySignatures(ty.Lookup("f"), ((), self.anything))
    self.assertHasOnlySignatures(ty.Lookup("g"), ((), self.anything))
    self.assertHasOnlySignatures(ty.Lookup("h"), ((), self.anything))

  def test_dict_literal(self):
    ty = self.Infer("""
      def f():
        return {"test": 1, "arg": 42}
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.str_int_dict))

  def test_dict_empty_constructor(self):
    ty = self.Infer("""
      def f():
        return dict()
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.nothing_nothing_dict))

  def test_dict_constructor(self):
    ty = self.Infer("""
      def f():
        return dict([(1, 2), (3, 4)])
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.int_int_dict))

  def test_dict_constructor2(self):
    ty = self.Infer("""
      def f():
        return dict([(1, "bar"), (2, "foo")])
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.int_str_dict))

  def test_dict_setitem(self):
    ty = self.Infer("""
      def f():
        d = {}
        d["test"] = 1
        d["arg"] = 42
        return d
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(
        ty.Lookup("f"),
        ((), self.str_int_dict))

  def test_dict_update(self):
    ty = self.Infer("""
      d = {}
      d.update({"a": 1}, b=2j)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      d = ...  # type: Dict[str, Union[int, complex]]
    """)

  def test_ambiguous_dict_update(self):
    ty = self.Infer("""
      d = {}
      d.update({"a": 1} if __random__ else {"b": 2j}, c=3.0)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Union
      d = ...  # type: Dict[str, Union[int, float, complex]]
    """)

  def test_for_iter(self):
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
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.intorstr))

  def test_overloading(self):
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
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int))

  def test_class_attr(self):
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
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int))

  def test_heterogeneous(self):
    ty = self.Infer("""
      def f():
        x = list()
        x.append(3)
        x.append("str")
        return x[0]
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.intorstr))

  def test_list_comprehension(self):
    # uses byte_LIST_APPEND
    ty = self.Infer("""
      def f():
        return [i for i in (1,2,3)]
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_list))

  def test_set_comprehension(self):
    # uses byte_SET_ADD
    ty = self.Infer("""
      def f():
        return {i for i in [1,2,3]}
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((),
                                  self.int_set))

  def test_empty_or_string(self):
    ty = self.Infer("""
      d = dict()
      d["a"] = "queen"
      entry = d["a"]
      open('%s' % entry, 'w')
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, str]
      entry = ...  # type: str
    """)

  def test_dict_init(self):
    ty = self.Infer("""
      def f():
        return dict([])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f() -> Dict[nothing, nothing]: ...
    """)

  def test_dict_tuple_init(self):
    ty = self.Infer("""
      def f():
        return dict([("foo", "foo")])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f() -> Dict[str, str]: ...
    """)

  def test_empty_tuple_as_arg(self):
    ty = self.Infer("""
      def f(x):
        if x:
          return isinstance(1, ())
        else:
          return 3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f(x) -> Union[bool, complex]: ...
    """)

  def test_empty_type_param_as_arg(self):
    ty = self.Infer("""
      def f():
        return sum(map(int, ()))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f() -> Any: ...
    """)

  def test_access_empty_dict_in_if(self):
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
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        next = ...  # type: NoneType

      def f(key) -> Foo: ...
    """)

  def test_cascade(self):
    ty = self.Infer("""
      if __random__:
        x = 3
      else:
        x = 3.14
      y = divmod(x, x)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      x = ...  # type: Union[float, int]
      y = ...  # type: Tuple[Union[float, int], Union[float, int]]
    """)

  def test_maybe_any(self):
    ty = self.Infer("""
      x = __any_object__
      x.as_integer_ratio()
      if x:
        x = 1
      y = divmod(x, 3.14)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Tuple
      x = ...  # type: Any
      y = ...  # type: Tuple[Any, Any]
    """)

  def test_index(self):
    ty = self.Infer("""
      def f():
        l = [__any_object__]
        if __random__:
          pos = None
        else:
          pos = 0
        l[pos] += 1
        return l
    """)
    self.assertTypesMatchPytd(ty, """
      # The element types aren't more precise since the solver doesn't know
      # which element of the list gets modified.
      def f() -> list: ...
    """)

  def test_circular_reference_list(self):
    ty = self.Infer("""
      def f():
        lst = []
        lst.append(lst)
        return lst
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f() -> List[list]: ...
    """)

  def test_circular_reference_dictionary(self):
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      # TODO(159069936): This should be "Dict[str, none]". s1 above can never
      # contain another dictionary.
      def f() -> Dict[str, Union[None, dict]]: ...
    """)

  def test_eq_operator_on_item_from_empty_dict(self):
    self.Infer("""
      d = {}
      d[1] == d[1]
    """, deep=False)

  def test_dict(self):
    ty, errors = self.InferWithErrors("""
      mymap = {'a': 3.14, 'b':1}
      a = mymap['a']
      b1 = mymap['b']
      c = mymap['foobar']  # key-error[e]
      mymap[str()] = 3j
      b2 = mymap['b']
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Union
      mymap = ...  # type: Dict[str, Union[int, float, complex]]
      a = ...  # type: float
      b1 = ...  # type: int
      c = ...  # type: Any
      b2 = ...  # type: Union[int, float, complex]
    """)
    self.assertErrorRegexes(errors, {"e": r"foobar"})

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
    _, errors = self.InferWithErrors("""
      v = {}
      v.__getitem__("a")  # key-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"'a'"})

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
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Union
      cache = ...  # type: Dict[str, Union[Dict[nothing, nothing], list]]
      def read(path) -> Any: ...
    """)

  def test_recursive_definition_and_conflict(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Generic[T]): ...
        class Baz(Foo[Baz], Bar[str]): ...
      """)
      self.Check("""
        import foo
        foo.Baz()
      """, pythonpath=[d.path])

  def test_foo(self):
    _ = self.Infer("""
      import collections
      class A(collections.namedtuple("_", ["a"])):
        pass
      class B(A, dict):
        pass
    """)


test_base.main(globals(), __name__ == "__main__")
