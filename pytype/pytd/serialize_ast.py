"""Converts pyi files to pickled asts and saves them to disk.

Used to speed up module importing. This is done by loading the ast and
serializing it to disk. Further users only need to read the serialized data from
disk, which is faster to digest than a pyi file.
"""
import cPickle
import sys

from pytype.pytd.parse import visitors

_PICKLE_PROTOCOL = cPickle.HIGHEST_PROTOCOL
_PICKLE_RECURSION_LIMIT_AST = 40000


class SerializableAst(object):
  """The data pickled to disk to save an ast.

  Attributes:
    ast: The TypeDeclUnit representing the serialized module.
    dependencies: A list of modules this AST depends on. The modules are
      represented as Fully Qualified names. E.g. foo.bar.module. This set will
      also contain the module being imported, if the module is not empty.
      Therefore it might be different from the set found by
      visitors.CollectDependencies in
      load_pytd._load_and_resolve_ast_dependencies.
    modified_class_types: A list of ClassType nodes which had their cls
      attribute replaced. This is used as an index into the tree so that a
      reader does not need to iterate over the tree.
  """

  def __init__(self, ast, dependencies, modified_class_types):
    self.ast = ast
    self.dependencies = dependencies
    self.modified_class_types = modified_class_types


class RemoveClassTypeReferencesVisitor(visitors.Visitor):
  """Removes all references outside of the local module.

  Before pickling references outside the ast need to be replaced.
  This is done to avoid creating instances of the foreign modules during loading
  of the pickled modules.
  It is a performance optimization, from a correctness point of view it would be
  fine to replace the loaded modules with the local versions in the process
  reading the pickled file. This would however serialize a lot of data, which is
  discarded later.

  This visitor modifies the AST in place as replacing the ClassTypes with
  NamedTypes would mean that the parent needs to be rebuilt.
  """

  def __init__(self):
    super(RemoveClassTypeReferencesVisitor, self).__init__()
    # A dictionary which is used to remember which nodes have already been
    # replaced. It maps the id() of a node to the node. This is needed as the
    # class_type equals is only comparing a subset of fields.
    self._all_class_types = []

  def EnterClassType(self, class_type):
    class_type.cls = None
    self._all_class_types.append(class_type)

  def GetAllClassTypes(self):
    return self._all_class_types


def StoreAst(ast, filename):
  """Loads and stores an ast to disk.

  Args:
    ast: The pytd.TypeDeclUnit to save to disk.
    filename: The filename for the pickled output

  Returns:
    True iff the save operation was successful.
  """
  # Collect dependencies
  deps = visitors.CollectDependencies()
  ast.Visit(deps)
  dependencies = deps.modules or set()

  # Clean external references
  visitor = RemoveClassTypeReferencesVisitor()
  ast.Visit(visitor)
  modified_class_types = visitor.GetAllClassTypes()

  serializable_ast = SerializableAst(ast, dependencies, modified_class_types)

  DumpData(serializable_ast, filename)
  return True


def LoadPickle(filename):
  with open(filename, "rb") as fi:
    return cPickle.load(fi)


def DumpData(data, filename):
  with open(filename, "wb") as fi:
    recursion_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(_PICKLE_RECURSION_LIMIT_AST)
    try:
      cPickle.dump(data, fi, _PICKLE_PROTOCOL)
    finally:
      sys.setrecursionlimit(recursion_limit)
