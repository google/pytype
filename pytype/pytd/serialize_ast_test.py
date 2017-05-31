import os
import pickle

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import serialize_ast
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import visitors

import unittest


class SerializeAstTest(unittest.TestCase):

  PYTHON_VERSION = (2, 7)

  def setUp(self):
    self.options = config.Options.create(python_version=self.PYTHON_VERSION)

  def _StoreAst(self, temp_dir, module_name, pickled_ast_filename):
    ast, loader = self._GetAst(temp_dir=temp_dir, module_name=module_name)
    serialize_ast.StoreAst(ast, pickled_ast_filename)
    module_map = {name: module.ast
                  for name, module in loader._modules.items()}

    return module_map

  def _GetAst(self, temp_dir, module_name, src=None):
    src = src or ("""
        import module2
        from typing import List

        constant = True

        x = List[int]
        b = List[int]

        class SomeClass(object):
          def __init__(self, a: module2.ObjectMod2):
            pass

        def ModuleFunction():
          pass
    """)
    pyi_filename = temp_dir.create_file("module1.pyi", src)
    temp_dir.create_file("module2.pyi", """
        class ObjectMod2(object):
          def __init__(self):
            pass
    """)

    self.options.tweak(pythonpath=[temp_dir.path])
    self.options.tweak(module_name=module_name)
    self.options.tweak(input=pyi_filename)
    loader = load_pytd.Loader(base_module=None, options=self.options)
    ast = loader.load_file(self.options.module_name, self.options.input)
    return ast, loader

  def testFindClassTypesVisitor(self):
    module_name = "foo.bar"
    with utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name)
    indexer = serialize_ast.FindClassTypesVisitor()
    ast.Visit(indexer)

    self.assertEquals(len(indexer.class_type_nodes), 9)

  def testNodeIndexVisitorUsage(self):
    """Confirms that the node index is used.

    This removes the first node from the class_type_nodes list and checks that
    that node is not updated by ProcessAst.
    """
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      del module_map[module_name]
      serialized_ast = pytd_utils.LoadPickle(pickled_ast_filename)

      # The sorted makes the testcase more deterministic.
      serialized_ast.class_type_nodes = sorted(
          serialized_ast.class_type_nodes)[1:]
      loaded_ast = serialize_ast.ProcessAst(serialized_ast, module_map)

      with self.assertRaisesRegexp(
          ValueError, "Unresolved class: '__builtin__.NoneType'"):
        loaded_ast.Visit(visitors.VerifyLookup())

  def testRenameModule(self):
    module_name = "foo.bar"
    with utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name)

    new_ast = ast.Visit(serialize_ast.RenameModuleVisitor(module_name,
                                                          "other.name"))

    self.assertEquals("other.name", new_ast.name)
    self.assertTrue(new_ast.Lookup("other.name.SomeClass"))
    self.assertTrue(new_ast.Lookup("other.name.constant"))
    self.assertTrue(new_ast.Lookup("other.name.ModuleFunction"))

    with self.assertRaises(KeyError):
      new_ast.Lookup("foo.bar.SomeClass")

  def testRenameModuleWithTypeParameter(self):
    module_name = "foo.bar"
    src = """
      import typing

      T = TypeVar('T')

      class SomeClass(typing.Generic[T]):
        def __init__(self, foo: T) -> None:
          pass
    """
    with utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name, src=src)
    new_ast = ast.Visit(serialize_ast.RenameModuleVisitor(module_name,
                                                          "other.name"))

    some_class = new_ast.Lookup("other.name.SomeClass")
    self.assertTrue(some_class)
    init_function = some_class.Lookup("__init__")
    self.assertTrue(init_function)
    self.assertEquals(len(init_function.signatures), 1)
    signature, = init_function.signatures
    _, param2 = signature.params
    self.assertEquals(param2.type.scope, "other.name.SomeClass")

  def testPickle(self):
    with utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name="foo.bar.module1")
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")

      result = serialize_ast.StoreAst(ast, pickled_ast_filename)

      self.assertTrue(result)
      with open(pickled_ast_filename, "rb") as fi:
        serialized_ast = pickle.load(fi)
      self.assertTrue(serialized_ast.ast)
      self.assertEquals(serialized_ast.dependencies,
                        {"__builtin__", "module2", "foo.bar.module1"})

  def testLoadTopLevel(self):
    """Tests that a pickled file can be read."""
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      original_ast = module_map[module_name]
      del module_map[module_name]
      loaded_ast = serialize_ast.ProcessAst(
          pytd_utils.LoadPickle(pickled_ast_filename),
          module_map)

      self.assertTrue(loaded_ast)
      self.assertTrue(loaded_ast is not original_ast)
      self.assertEquals(loaded_ast.name, module_name)
      self.assertTrue(original_ast.ASTeq(loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def testLoadWithSameModuleName(self):
    """Explicitly set the module name and reload with the same name.

    The difference to testLoadTopLevel is that the module name does not match
    the filelocation.
    """
    with utils.Tempdir() as d:
      module_name = "foo.bar.module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      original_ast = module_map[module_name]
      del module_map[module_name]

      loaded_ast = serialize_ast.ProcessAst(
          pytd_utils.LoadPickle(pickled_ast_filename),
          module_map)

      self.assertTrue(loaded_ast)
      self.assertTrue(loaded_ast is not original_ast)
      self.assertEquals(loaded_ast.name, "foo.bar.module1")
      self.assertTrue(original_ast.ASTeq(loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def testUnrestorableDependencyErrorWithModuleIndex(self):
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      module_map = {}  # Remove module2

      with self.assertRaises(serialize_ast.UnrestorableDependencyError):
        serialize_ast.ProcessAst(
            pytd_utils.LoadPickle(pickled_ast_filename),
            module_map)

  def testUnrestorableDependencyErrorWithoutModuleIndex(self):
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      module_map = {}  # Remove module2

      loaded_ast = pytd_utils.LoadPickle(pickled_ast_filename)
      loaded_ast.modified_class_types = None  # Remove the index
      with self.assertRaises(serialize_ast.UnrestorableDependencyError):
        serialize_ast.ProcessAst(loaded_ast, module_map)

  def testLoadWithDifferentModuleName(self):
    with utils.Tempdir() as d:
      original_module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, original_module_name, pickled_ast_filename)
      original_ast = module_map[original_module_name]
      del module_map[original_module_name]

      new_module_name = "wurstbrot.module2"
      serializable_ast = pytd_utils.LoadPickle(pickled_ast_filename)
      serialize_ast.EnsureAstName(serializable_ast, new_module_name)
      loaded_ast = serialize_ast.ProcessAst(serializable_ast, module_map)

      self.assertTrue(loaded_ast)
      self.assertTrue(loaded_ast is not original_ast)
      self.assertEquals(loaded_ast.name, new_module_name)
      loaded_ast.Visit(visitors.VerifyLookup())
      self.assertFalse(original_ast.ASTeq(loaded_ast))
      ast_new_module, _ = self._GetAst(temp_dir=d, module_name=new_module_name)
      self.assertTrue(ast_new_module.ASTeq(loaded_ast))

  def testStoreRemovesInit(self):
    with utils.Tempdir() as d:
      original_module_name = "module1.__init__"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")

      module_map = self._StoreAst(d, original_module_name, pickled_ast_filename)
      serializable_ast = pytd_utils.LoadPickle(pickled_ast_filename)

      expected_name = "module1"
      # Check that the module had the expected name before.
      self.assertTrue(original_module_name in module_map)
      # Check that module1 wasn't created before storing.
      self.assertTrue(expected_name not in module_map)
      # Check that the saved ast had its name changed.
      self.assertEquals(serializable_ast.ast.name, expected_name)


if __name__ == "__main__":
  unittest.main()
