"""Tests for collections_overlay.py."""

from pytype.overlays import collections_overlay
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_base

import unittest


class NamedTupleAstTest(test_base.UnitTest):
  """Test collection_overlay's namedtuple AST generation."""

  def _namedtuple_ast(self, name, fields):
    return collections_overlay.namedtuple_ast(name, fields, self.python_version)

  def test_basic(self):
    ast = self._namedtuple_ast("X", [])
    typeparam, = ast.type_params
    self.assertEqual("X", typeparam.bound.name)
    nt = ast.Lookup("X")
    self.assertEqual("def __init__(self, *args, **kwargs) -> None: ...",
                     pytd_utils.Print(nt.Lookup("__init__")))
    make_sig, = nt.Lookup("_make").signatures
    replace_sig, = nt.Lookup("_replace").signatures
    self.assertEqual("_TX", make_sig.return_type.name)
    self.assertEqual("_TX", replace_sig.return_type.name)

  def test_no_fields(self):
    nt = self._namedtuple_ast("X", []).Lookup("X")
    self.assertEqual("Tuple[()]",
                     pytd_utils.Print(nt.Lookup("_fields").type))
    getnewargs_sig, = nt.Lookup("__getnewargs__").signatures
    self.assertEqual("Tuple[()]",
                     pytd_utils.Print(getnewargs_sig.return_type))
    self.assertEqual("def __new__(cls: Type[_TX]) -> _TX: ...",
                     pytd_utils.Print(nt.Lookup("__new__")))

  def test_fields(self):
    nt = self._namedtuple_ast("X", ["y", "z"]).Lookup("X")
    self.assertEqual("Tuple[str, str]",
                     pytd_utils.Print(nt.Lookup("_fields").type))
    self.assertEqual(pytd.AnythingType(), nt.Lookup("y").type)
    self.assertEqual(pytd.AnythingType(), nt.Lookup("z").type)
    getnewargs_sig, = nt.Lookup("__getnewargs__").signatures
    self.assertEqual("Tuple[Any, Any]",
                     pytd_utils.Print(getnewargs_sig.return_type))
    self.assertEqual("def __new__(cls: Type[_TX], y, z) -> _TX: ...",
                     pytd_utils.Print(nt.Lookup("__new__")))

  def test_name(self):
    # The generated name has to be different from the official name, or we'll
    # end up with nonsense like X = X.
    self.assertNotEqual("X", collections_overlay.namedtuple_name("X", []))
    # Two namedtuple instances should have the same name iff the instances are
    # the same.
    self.assertNotEqual(collections_overlay.namedtuple_name("X", []),
                        collections_overlay.namedtuple_name("X", ["a"]))
    self.assertNotEqual(collections_overlay.namedtuple_name("X", ["a"]),
                        collections_overlay.namedtuple_name("X", ["b"]))


if __name__ == "__main__":
  unittest.main()
