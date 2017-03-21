import os
import pickle

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import serialize_ast

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

  def testPickle(self):
    with utils.Tempdir() as d:
      pyi_filename = d.create_file("module1.pyi", """
          import module2
          from typing import List

          x = List[int]
          b = List[int]

          class SomeClass(object):
            def __init__(self, a: module2.ObjectMod2):
              pass

      """)
      d.create_file("module2.pyi", """
          class ObjectMod2(object):
            def __init__(self):
              pass
      """)

      pickled_ast_filename = os.path.join(d.path, "module1.pyi.pickled")
      self.options.tweak(pythonpath=[d.path])
      self.options.tweak(module_name="foo.bar.module1")
      self.options.tweak(input=pyi_filename)
      loader = load_pytd.Loader(base_module=None, options=self.options)
      ast = loader.load_file(self.options.module_name, self.options.input)
      result = serialize_ast.StoreAst(ast, pickled_ast_filename)
      self.assertTrue(result)
      with open(pickled_ast_filename, "r") as fi:
        serialized_ast = pickle.load(fi)

      self.assertTrue(serialized_ast.ast)
      self.assertEquals(serialized_ast.dependencies,
                        {"__builtin__", "module2", "foo.bar.module1"})

      self.assertEquals(len(serialized_ast.modified_class_types), 8)
      self.assertEquals(set(serialized_ast.modified_class_types), {
          pytd.ClassType("foo.bar.module1.SomeClass"),  # class SomeClass(...)
          pytd.ClassType("__builtin__.object"),  # class SomeClass(Object)
          pytd.ClassType("__builtin__.list"),  # x = List[]
          pytd.ClassType("__builtin__.list"),  # b = List[]
          pytd.ClassType("__builtin__.int"),  # x = List[int]
          pytd.ClassType("module2.ObjectMod2"),  # a: module2.ObjectMod2
          pytd.ClassType("__builtin__.int"),  # b = List[int]
          pytd.ClassType("__builtin__.NoneType")}  # def __init__ return
                       )


if __name__ == "__main__":
  unittest.main()
