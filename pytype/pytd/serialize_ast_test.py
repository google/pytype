import os
import pickle

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import serialize_ast
from pytype.pytd.parse import visitors

import unittest


class RemoveClassTypeReferencesVisitorTest(unittest.TestCase):

  def testClsRemoval(self):
    ty_a = pytd.ClassType("A")
    cls = pytd.ClassType("B")
    ty_a.cls = cls
    visitor = serialize_ast.RemoveClassTypeReferencesVisitor()
    ty_a.Visit(visitor)
    self.assertIsNone(ty_a.cls)
    self.assertEquals([ty_a], visitor.GetAllClassTypes())


class ImportPathsTest(unittest.TestCase):

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
      self.assertEquals(len(serialized_ast.modified_class_types), 9)
      self.assertEquals(set(serialized_ast.modified_class_types), {
          pytd.ClassType("foo.bar.module1.SomeClass"),  # class SomeClass(...)
          pytd.ClassType("__builtin__.object"),  # class SomeClass(Object)
          pytd.ClassType("__builtin__.bool"),  # constant = True
          pytd.ClassType("__builtin__.list"),  # x = List[]
          pytd.ClassType("__builtin__.list"),  # b = List[]
          pytd.ClassType("__builtin__.int"),  # x = List[int]
          pytd.ClassType("module2.ObjectMod2"),  # a: module2.ObjectMod2
          pytd.ClassType("__builtin__.int"),  # b = List[int]
          pytd.ClassType("__builtin__.NoneType")}  # def __init__ return
                       )

  def testLoadTopLevel(self):
    """Tests that a pickled file can be read."""
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      original_ast = module_map[module_name]
      del module_map[module_name]
      loaded_ast = serialize_ast.ProcessAst(
          serialize_ast.LoadPickle(pickled_ast_filename),
          module_map,
          module_name)

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
          serialize_ast.LoadPickle(pickled_ast_filename),
          module_map,
          module_name)

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
            serialize_ast.LoadPickle(pickled_ast_filename),
            module_map,
            module_name)

  def testUnrestorableDependencyErrorWithoutModuleIndex(self):
    with utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      module_map = {}  # Remove module2

      loaded_ast = serialize_ast.LoadPickle(pickled_ast_filename)
      loaded_ast.modified_class_types = None  # Remove the index
      with self.assertRaises(serialize_ast.UnrestorableDependencyError):
        serialize_ast.ProcessAst(loaded_ast, module_map, module_name)

  def testLoadWithDifferentModuleName(self):
    with utils.Tempdir() as d:
      original_module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, original_module_name, pickled_ast_filename)
      original_ast = module_map[original_module_name]
      del module_map[original_module_name]

      new_module_name = "wurstbrot.module2"
      loaded_ast = serialize_ast.ProcessAst(
          serialize_ast.LoadPickle(pickled_ast_filename),
          module_map,
          new_module_name)

      self.assertTrue(loaded_ast)
      self.assertTrue(loaded_ast is not original_ast)
      self.assertEquals(loaded_ast.name, new_module_name)
      loaded_ast.Visit(visitors.VerifyLookup())
      self.assertFalse(original_ast.ASTeq(loaded_ast))
      ast_new_module, _ = self._GetAst(temp_dir=d, module_name=new_module_name)
      self.assertTrue(ast_new_module.ASTeq(loaded_ast))


if __name__ == "__main__":
  unittest.main()
