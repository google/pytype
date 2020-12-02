"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd).

File 3/3. Split into parts to enable better test parallelism.
"""


from pytype import abstract_utils
from pytype import file_utils
from pytype.tests import test_base


class BuiltinTests3(test_base.TargetIndependentTest):
  """Tests for builtin methods and classes."""

  def test_super_attribute(self):
    ty = self.Infer("""
      x = super.__name__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
    """)

  def test_slice(self):
    ty = self.Infer("""
      x1 = [1,2,3][1:None]
      x2 = [1,2,3][None:2]
      x3 = [1,2,3][None:None]
      x4 = [1,2,3][1:3:None]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[int]
      x2 = ...  # type: List[int]
      x3 = ...  # type: List[int]
      x4 = ...  # type: List[int]
    """)

  def test_slice_attributes(self):
    ty = self.Infer("""
      v = slice(1)
      start = v.start
      stop = v.stop
      step = v.step
      indices = v.indices(0)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Tuple
      v = ...  # type: slice
      start = ...  # type: Optional[int]
      stop = ...  # type: Optional[int]
      step = ...  # type: Optional[int]
      indices = ...  # type: Tuple[int, int, int]
    """)

  def test_next_function(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: Union[int, str]
    """)

  def test_implicit_typevar_import(self):
    ty, _ = self.InferWithErrors("""
      v = %s  # name-error
    """ % abstract_utils.T)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      v = ...  # type: Any
    """)

  def test_explicit_typevar_import(self):
    self.Check("""
      from __builtin__ import _T
      _T
    """)

  def test_class_of_type(self):
    ty = self.Infer("""
      v = int.__class__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      v = ...  # type: Type[type]
    """)

  @test_base.skip("broken")
  def test_clear(self):
    ty = self.Infer("""
      x = {1, 2}
      x.clear()
      y = {"foo": 1}
      y.clear()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set
      x = ...  # type: Set[nothing]
      y = ...  # type: Dict[nothing, nothing]
    """)

  def test_cmp(self):
    ty = self.Infer("""
      if not cmp(4, 4):
        x = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def test_repr(self):
    ty = self.Infer("""
      if repr("hello world"):
        x = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def test_int_init(self):
    _, errors = self.InferWithErrors("""
      int()
      int(0)
      int("0")
      int("0", 10)
      int(u"0")
      int(u"0", 10)
      int(0, 1, 2)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"1.*4"})

  def test_newlines(self):
    with file_utils.Tempdir() as d:
      d.create_file("newlines.txt", """
          1
          2
          3
          """)
      self.Check("""
          l = []
          with open("newlines.txt", "rU") as f:
            for line in f:
              l.append(line)
            newlines = f.newlines
          """)

  def test_init_with_unicode(self):
    self.Check("""
        int(u"123.0")
        float(u"123.0")
        complex(u"123.0")
    """)

  def test_io_write(self):
    self.Check("""
        import sys
        sys.stdout.write("hello world")
    """)

  def test_binary_io_write(self):
    self.Check("""
      with open('foo', 'wb') as f:
        f.write(bytearray([1, 2, 3]))
    """)

  def test_hasattr_none(self):
    self.assertNoCrash(self.Check, "hasattr(int, None)")

  def test_number_attrs(self):
    ty = self.Infer("""
      a = (42).denominator
      b = (42).numerator
      c = (42).real
      d = (42).imag
      e = (3.14).conjugate()
      f = (3.14).is_integer()
      g = (3.14).real
      h = (3.14).imag
      i = (2j).conjugate()
      j = (2j).real
      k = (2j).imag
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: int
      d = ...  # type: int
      e = ...  # type: float
      f = ...  # type: bool
      g = ...  # type: float
      h = ...  # type: float
      i = ...  # type: complex
      j = ...  # type: float
      k = ...  # type: float
    """)

  def test_builtins(self):
    # This module doesn't exist, on Python 2. However, it exists in typeshed, so
    # make sure that we don't break (report pyi-error) when we import it.
    self.Check("""
      import builtins  # pytype: disable=import-error
    """)

  def test_special_builtin_types(self):
    self.InferWithErrors("""
      isinstance(1, int)
      isinstance(1, "no")  # wrong-arg-types
      issubclass(int, object)
      issubclass(0, 0)  # wrong-arg-types
      issubclass(int, 0)  # wrong-arg-types
      hasattr(str, "upper")
      hasattr(int, int)  # wrong-arg-types
      """)

  def test_unpack_list(self):
    ty = self.Infer("""
      x = [1, ""]
      a, b = x
      x.append(2)
      c, d, e = x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      x = ...  # type: List[Union[int, str]]
      a = ...  # type: int
      b = ...  # type: str
      c = ...  # type: Union[int, str]
      d = ...  # type: Union[int, str]
      e = ...  # type: Union[int, str]
    """)

  def test_bytearray_setitem(self):
    self.Check("""
      ba = bytearray(b"hello")
      ba[0] = 106
      ba[4:] = [121, 102, 105, 115, 104]
      ba[4:] = b"yfish"
      ba[4:] = bytearray("yfish")
      ba[:5] = b""
      ba[1:2] = b"la"
      ba[2:3:2] = b"u"
    """)

  def test_bytearray_setitem_py3(self):
    self.Check("""
      ba = bytearray(b"hello")
      ba[0] = 106
      ba[:1] = [106]
      ba[:1] = b"j"
      ba[:1] = bytearray(b"j")
      ba[:1] = memoryview(b"j")
      ba[4:] = b"yfish"
      ba[0:5] = b""
      ba[1:4:2] = b"at"
    """)

  def test_from_hex(self):
    ty = self.Infer("""
      f = float.fromhex("feed")
      b = bytearray.fromhex("beef")
    """)
    self.assertTypesMatchPytd(ty, """
      f = ...  # type: float
      b = ...  # type: bytearray
    """)

  def test_none_length(self):
    errors = self.CheckWithErrors("len(None)  # wrong-arg-types[e]")
    self.assertErrorRegexes(errors, {"e": r"Sized.*None"})

  def test_sequence_length(self):
    self.Check("""
      len("")
      len(u"")
      len(bytearray())
      len([])
      len(())
      len(frozenset())
      len(range(0))
    """)

  def test_mapping_length(self):
    self.Check("""
      len({})
    """)

  def test_print_bare_type(self):
    ty = self.Infer("""
      from typing import Any, Dict, Type
      d1 = {}  # type: Dict[str, type]
      d2 = {}  # type: Dict[str, Type[Any]]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[str, type]
      d2 = ...  # type: Dict[str, type]
    """)

  def test_get_function_attr(self):
    self.Check("getattr(lambda: None, '__defaults__')")

  def test_str_startswith(self):
    self.Check("""
      s = "some str"
      s.startswith("s")
      s.startswith(("s", "t"))
      s.startswith("a", start=1, end=2)
    """)

  def test_str_endswith(self):
    self.Check("""
      s = "some str"
      s.endswith("r")
      s.endswith(("r", "t"))
      s.endswith("a", start=1, end=2)
    """)

  def test_path(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/__init__.py")
      self.Check("""
        import foo
        __path__, foo.__path__
      """, pythonpath=[d.path])

  def test_del_byte_array_slice(self):
    self.Check("""
      ba = bytearray(b"hello")
      del ba[0:2]
    """)

  def test_input(self):
    self.Check("""
      input()
      input('input: ')
    """)

  def test_set_default_error(self):
    ty, errors = self.InferWithErrors("""
      x = {}
      y = x.setdefault()  # wrong-arg-count[e1]
      z = x.setdefault(1, 2, 3, *[])  # wrong-arg-count[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      x = ...  # type: Dict[nothing, nothing]
      y = ...  # type: Any
      z = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e1": r"2.*0", "e2": r"2.*3"})

  def test_tuple(self):
    ty = self.Infer("""
      def f(x, y):
        return y
      def g():
        args = (4, )
        return f(3, *args)
      g()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _T1 = TypeVar("_T1")
      def f(x, y: _T1) -> _T1: ...
      def g() -> int: ...
    """)

  def test_str_join_error(self):
    errors = self.CheckWithErrors("', '.join([1, 2, 3])  # wrong-arg-types[e]")
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*Iterable\[str\].*Actual.*List\[int\]"})

  def test_int_protocols(self):
    self.Check("""
      class Foo:
        def __int__(self):
          return 0
      class Bar:
        def __trunc__(self):
          return 0
      int(Foo())
      int(Bar())
    """)


test_base.main(globals(), __name__ == "__main__")
