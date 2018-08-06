import os
import pickle

from pytype import file_utils
from pytype import load_pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors

import unittest


class SerializeAstTest(unittest.TestCase):

  PYTHON_VERSION = (2, 7)

  def _StoreAst(
      self, temp_dir, module_name, pickled_ast_filename, ast=None, loader=None):
    if not (ast and loader):
      ast, loader = self._GetAst(temp_dir=temp_dir, module_name=module_name)
    serialize_ast.StoreAst(ast, pickled_ast_filename)
    module_map = {name: module.ast
                  for name, module in loader._modules.items()}

    return module_map

  def _GetAst(self, temp_dir, module_name, src=None):
    src = src or ("""
        import module2
        from module2 import f
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
        import UserDict
        def f() -> UserDict.UserDict: ...
        class ObjectMod2(object):
          def __init__(self):
            pass
    """)

    loader = load_pytd.Loader(base_module=None,
                              python_version=self.PYTHON_VERSION,
                              pythonpath=[temp_dir.path])
    ast = loader.load_file(module_name, pyi_filename)
    # serialize_ast.StoreAst sorts the ast for determinism, so we should do the
    # same to the original ast to do pre- and post-pickling comparisons.
    loader._modules[module_name].ast = ast = ast.Visit(
        visitors.CanonicalOrderingVisitor())
    return ast, loader

  def testFindClassTypesVisitor(self):
    module_name = "foo.bar"
    with file_utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name)
    indexer = serialize_ast.FindClassAndFunctionTypesVisitor()
    ast.Visit(indexer)

    self.assertEqual(len(indexer.class_type_nodes), 9)

  def testNodeIndexVisitorUsage(self):
    """Confirms that the node index is used.

    This removes the first node from the class_type_nodes list and checks that
    that node is not updated by ProcessAst.
    """
    with file_utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      del module_map[module_name]
      serialized_ast = pytd_utils.LoadPickle(pickled_ast_filename)

      # The sorted makes the testcase more deterministic.
      serialized_ast = serialized_ast.Replace(class_type_nodes=sorted(
          serialized_ast.class_type_nodes)[1:])
      loaded_ast = serialize_ast.ProcessAst(serialized_ast, module_map)

      with self.assertRaisesRegexp(
          ValueError, "Unresolved class: '__builtin__.NoneType'"):
        loaded_ast.Visit(visitors.VerifyLookup())

  def testRenameModule(self):
    module_name = "foo.bar"
    with file_utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name)

    new_ast = ast.Visit(serialize_ast.RenameModuleVisitor(module_name,
                                                          "other.name"))

    self.assertEqual("other.name", new_ast.name)
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
    with file_utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name, src=src)
    new_ast = ast.Visit(serialize_ast.RenameModuleVisitor(module_name,
                                                          "other.name"))

    some_class = new_ast.Lookup("other.name.SomeClass")
    self.assertTrue(some_class)
    init_function = some_class.Lookup("__init__")
    self.assertTrue(init_function)
    self.assertEqual(len(init_function.signatures), 1)
    signature, = init_function.signatures
    _, param2 = signature.params
    self.assertEqual(param2.type.scope, "other.name.SomeClass")

  def testRenameInitModule(self):
    module_name = "foo.bar"
    src = """
      def f() -> foo.bar.baz.Foo: ...
    """
    with file_utils.Tempdir() as d:
      d.create_file("foo/__init__.pyi", "")
      d.create_file("foo/bar/__init__.pyi", "")
      d.create_file("foo/bar/baz.pyi", """
        class Foo(object): ...
      """)
      ast, _ = self._GetAst(temp_dir=d, module_name=module_name, src=src)
    new_ast = ast.Visit(
        serialize_ast.RenameModuleVisitor(module_name, "other.name"))
    f = new_ast.Lookup("other.name.f")
    ret = f.signatures[0].return_type
    self.assertEqual(ret.name, "foo.bar.baz.Foo")

  def testPickle(self):
    with file_utils.Tempdir() as d:
      ast, _ = self._GetAst(temp_dir=d, module_name="foo.bar.module1")
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")

      result = serialize_ast.StoreAst(ast, pickled_ast_filename)

      self.assertIsNone(result)
      with open(pickled_ast_filename, "rb") as fi:
        serialized_ast = pickle.load(fi)
      self.assertTrue(serialized_ast.ast)
      self.assertEqual(serialized_ast.dependencies,
                       ["__builtin__", "foo.bar.module1", "module2"])

  def testUnrestorableChild(self):
    # Assume .cls in a ClassType X in module1 was referencing something for
    # which, Visitors.LookupExternalTypes returned AnythingType.
    # Now if something in module1 is referencing X external types need to be
    # resolved before local types, so that we can resolve local types to the
    # correct ClassType, as the ClassType instance changes, if .cls can not be
    # filled and instead AnythingType is used.

    class RenameVisitor(visitors.Visitor):

      def __init__(self, *args, **kwargs):
        super(RenameVisitor, self).__init__(*args, **kwargs)
        self._init = False

      def EnterFunction(self, func):
        if func.name == "__init__":
          self._init = True
          return None
        return False

      def LeaveFunction(self, func):
        self._init = False

      def VisitClassType(self, cls_type):
        if self._init:
          cls_type = cls_type.Replace(name="other_module.unknown_Reference")
          # Needs to be copied manually as it is not part of the NamedTuple.
          cls_type.cls = None
        return cls_type

    with file_utils.Tempdir() as d:
      src = ("""
        import other_module
        x = other_module.UnusedReferenceNeededToKeepTheImport

        class SomeClass(object):
          def __init__(will_be_replaced_with_visitor) -> None:
            pass

        def func(a:SomeClass) -> None:
          pass
      """)
      d.create_file("other_module.pyi", """
          from typing import Any
          def __getattr__(self, name) -> Any: ..."""
                   )
      ast, loader = self._GetAst(
          temp_dir=d, module_name="module1", src=src)

      ast = ast.Visit(RenameVisitor())

      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(
          d, "module1", pickled_ast_filename, ast=ast, loader=loader)
      del module_map["module1"]

      serialized_ast = pytd_utils.LoadPickle(pickled_ast_filename)
      loaded_ast = serialize_ast.ProcessAst(
          serialized_ast, module_map)
      # Look up the "SomeClass" in "def func(a: SomeClass), then run
      # VerifyLookup on it. We can't run VerifyLookup on the root node, since
      # visitors don't descend into the "cls" attribute of ClassType.
      cls = loaded_ast.functions[0].signatures[0].params[0].type.cls
      cls.Visit(visitors.VerifyLookup())

  def testLoadTopLevel(self):
    """Tests that a pickled file can be read."""
    with file_utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      original_ast = module_map[module_name]
      del module_map[module_name]
      loaded_ast = serialize_ast.ProcessAst(
          pytd_utils.LoadPickle(pickled_ast_filename),
          module_map)

      self.assertTrue(loaded_ast)
      self.assertIsNot(loaded_ast, original_ast)
      self.assertEqual(loaded_ast.name, module_name)
      self.assertTrue(original_ast.ASTeq(loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def testLoadWithSameModuleName(self):
    """Explicitly set the module name and reload with the same name.

    The difference to testLoadTopLevel is that the module name does not match
    the filelocation.
    """
    with file_utils.Tempdir() as d:
      module_name = "foo.bar.module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      original_ast = module_map[module_name]
      del module_map[module_name]

      loaded_ast = serialize_ast.ProcessAst(
          pytd_utils.LoadPickle(pickled_ast_filename),
          module_map)

      self.assertTrue(loaded_ast)
      self.assertIsNot(loaded_ast, original_ast)
      self.assertEqual(loaded_ast.name, "foo.bar.module1")
      self.assertTrue(original_ast.ASTeq(loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def testUnrestorableDependencyErrorWithModuleIndex(self):
    with file_utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      module_map = {}  # Remove module2

      with self.assertRaises(serialize_ast.UnrestorableDependencyError):
        serialize_ast.ProcessAst(
            pytd_utils.LoadPickle(pickled_ast_filename),
            module_map)

  def testUnrestorableDependencyErrorWithoutModuleIndex(self):
    with file_utils.Tempdir() as d:
      module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, module_name, pickled_ast_filename)
      module_map = {}  # Remove module2

      loaded_ast = pytd_utils.LoadPickle(pickled_ast_filename)
      loaded_ast.modified_class_types = None  # Remove the index
      with self.assertRaises(serialize_ast.UnrestorableDependencyError):
        serialize_ast.ProcessAst(loaded_ast, module_map)

  def testLoadWithDifferentModuleName(self):
    with file_utils.Tempdir() as d:
      original_module_name = "module1"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      module_map = self._StoreAst(d, original_module_name, pickled_ast_filename)
      original_ast = module_map[original_module_name]
      del module_map[original_module_name]

      new_module_name = "wurstbrot.module2"
      serializable_ast = pytd_utils.LoadPickle(pickled_ast_filename)
      serializable_ast = serialize_ast.EnsureAstName(
          serializable_ast, new_module_name, fix=True)
      loaded_ast = serialize_ast.ProcessAst(serializable_ast, module_map)

      self.assertTrue(loaded_ast)
      self.assertIsNot(loaded_ast, original_ast)
      self.assertEqual(loaded_ast.name, new_module_name)
      loaded_ast.Visit(visitors.VerifyLookup())
      self.assertFalse(original_ast.ASTeq(loaded_ast))
      ast_new_module, _ = self._GetAst(temp_dir=d, module_name=new_module_name)
      self.assertTrue(ast_new_module.ASTeq(loaded_ast))

  def testStoreRemovesInit(self):
    with file_utils.Tempdir() as d:
      original_module_name = "module1.__init__"
      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")

      module_map = self._StoreAst(d, original_module_name, pickled_ast_filename)
      serializable_ast = pytd_utils.LoadPickle(pickled_ast_filename)

      expected_name = "module1"
      # Check that the module had the expected name before.
      self.assertIn(original_module_name, module_map)
      # Check that module1 wasn't created before storing.
      self.assertNotIn(expected_name, module_map)
      # Check that the saved ast had its name changed.
      self.assertEqual(serializable_ast.ast.name, expected_name)

  def testFunctionType(self):
    with file_utils.Tempdir() as d:
      foo = d.create_file("foo.pickle")
      module_map = self._StoreAst(d, "foo", foo, ast=self._GetAst(d, "foo"))
      p = pytd_utils.LoadPickle(foo)
      self.assertTrue(p.function_type_nodes)
      ast = serialize_ast.ProcessAst(p, module_map)
      f, = [a for a in ast.aliases if a.name == "foo.f"]
      signature, = f.type.function.signatures
      self.assertIsNotNone(signature.return_type.cls)


if __name__ == "__main__":
  unittest.main()
