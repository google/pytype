"""Converts pyi files to pickled asts and saves them to disk.

Used to speed up module importing. This is done by loading the ast and
serializing it to disk. Further users only need to read the serialized data from
disk, which is faster to digest than a pyi file.
"""

import collections

from pytype import utils
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors


class UnrestorableDependencyError(Exception):
  """If a dependency can't be restored in the current state."""


class FindClassAndFunctionTypesVisitor(visitors.Visitor):
  """Visitor to find class and function types."""

  def __init__(self):
    super().__init__()
    self.class_type_nodes = []
    self.function_type_nodes = []

  def EnterClassType(self, n):
    self.class_type_nodes.append(n)

  def EnterFunctionType(self, n):
    self.function_type_nodes.append(n)


SerializableTupleClass = collections.namedtuple(
    "_", ["ast", "dependencies", "late_dependencies",
          "class_type_nodes", "function_type_nodes"])


class SerializableAst(SerializableTupleClass):
  """The data pickled to disk to save an ast.

  Attributes:
    ast: The TypeDeclUnit representing the serialized module.
    dependencies: A list of modules this AST depends on. The modules are
      represented as Fully Qualified names. E.g. foo.bar.module. This set will
      also contain the module being imported, if the module is not empty.
      Therefore it might be different from the set found by
      visitors.CollectDependencies in
      load_pytd._load_and_resolve_ast_dependencies.
    class_type_nodes: A list of all the ClassType instances in ast or None. If
      this list is provided only the ClassType instances in the list will be
      visited and have their .cls set. If this attribute is None the whole AST
      will be visited and all found ClassType instances will have their .cls
      set.
  """
  Replace = SerializableTupleClass._replace  # pylint: disable=no-member,invalid-name


def StoreAst(ast, filename=None, open_function=open):
  """Loads and stores an ast to disk.

  Args:
    ast: The pytd.TypeDeclUnit to save to disk.
    filename: The filename for the pickled output. If this is None, this
      function instead returns the pickled string.
    open_function: A custom file opening function.

  Returns:
    The pickled string, if no filename was given. (None otherwise.)
  """
  if ast.name.endswith(".__init__"):
    ast = ast.Visit(visitors.RenameModuleVisitor(
        ast.name, ast.name.rsplit(".__init__", 1)[0]))
  # Collect dependencies
  deps = visitors.CollectDependencies()
  ast.Visit(deps)
  dependencies = deps.dependencies
  late_dependencies = deps.late_dependencies

  # Clean external references
  ast.Visit(visitors.ClearClassPointers())
  indexer = FindClassAndFunctionTypesVisitor()
  ast.Visit(indexer)
  ast = ast.Visit(visitors.CanonicalOrderingVisitor())
  return pytd_utils.SavePickle(
      SerializableAst(
          ast, sorted(dependencies.items()),
          sorted(late_dependencies.items()),
          sorted(indexer.class_type_nodes),
          sorted(indexer.function_type_nodes)),
      filename, open_function=open_function)


def EnsureAstName(ast, module_name, fix=False):
  """Verify that serializable_ast has the name module_name, or repair it.

  Args:
    ast: An instance of SerializableAst.
    module_name: The name under which ast.ast should be loaded.
    fix: If this function should repair the wrong name.

  Returns:
    The updated SerializableAst.
  """
  # The most likely case is module_name==raw_ast.name .
  raw_ast = ast.ast

  # module_name is the name from this run, raw_ast.name is the guessed name from
  # when the ast has been pickled.
  if fix and module_name != raw_ast.name:
    ast = ast.Replace(class_type_nodes=None, function_type_nodes=None)
    ast = ast.Replace(ast=raw_ast.Visit(
        visitors.RenameModuleVisitor(raw_ast.name, module_name)))
  else:
    assert module_name == raw_ast.name
  return ast


def ProcessAst(serializable_ast, module_map):
  """Postprocess a pickled ast.

  Postprocessing will either just fill the ClassType references from module_map
  or if module_name changed between pickling and loading rename the module
  internal references to the new module_name.
  Renaming is more expensive than filling references, as the whole AST needs to
  be rebuild.

  Args:
    serializable_ast: A SerializableAst instance.
    module_map: Used to resolve ClassType.cls links to already loaded modules.
      The loaded module will be added to the dict.

  Returns:
    A pytd.TypeDeclUnit, this is either the input raw_ast with the references
    set or a newly created AST with the new module_name and the references set.

  Raises:
    AssertionError: If module_name is already in module_map, which means that
      module_name is already loaded.
    UnrestorableDependencyError: If no concrete module exists in module_map for
      one of the references from the pickled ast.
  """
  # Module external and internal references need to be filled in different
  # steps. As a part of a local ClassType referencing an external cls, might be
  # changed structurally, if the external class definition used here is
  # different from the one used during serialization. Changing an attribute
  # (other than .cls) will trigger an recreation of the ClassType in which case
  # we need the reference to the new instance, which can only be known after all
  # external references are resolved.
  serializable_ast = _LookupClassReferences(
      serializable_ast, module_map, serializable_ast.ast.name)
  serializable_ast = FillLocalReferences(serializable_ast, {
      "": serializable_ast.ast,
      serializable_ast.ast.name: serializable_ast.ast})
  return serializable_ast.ast


def _LookupClassReferences(serializable_ast, module_map, self_name):
  """Fills .cls references in serializable_ast.ast with ones from module_map.

  Already filled references are not changed. References to the module self._name
  are not filled. Setting self_name=None will fill all references.

  Args:
    serializable_ast: A SerializableAst instance.
    module_map: Used to resolve ClassType.cls links to already loaded modules.
      The loaded module will be added to the dict.
    self_name: A string representation of a module which should not be resolved,
      for example: "foo.bar.module1" or None to resolve all modules.

  Returns:
    A SerializableAst with an updated .ast. .class_type_nodes is set to None
    if any of the Nodes needed to be regenerated.
  """

  class_lookup = visitors.LookupExternalTypes(module_map, self_name=self_name)
  raw_ast = serializable_ast.ast

  for node in (serializable_ast.class_type_nodes or ()):
    try:
      if node is not class_lookup.VisitClassType(node):
        serializable_ast = serializable_ast.Replace(class_type_nodes=None)
        break
    except KeyError as e:
      raise UnrestorableDependencyError(
          "Unresolved class: %r." % utils.message(e)) from e
  for node in (serializable_ast.function_type_nodes or ()):
    try:
      # Use VisitNamedType, even though this is a FunctionType. We want to
      # do a name lookup, to make sure this is still a function.
      if not isinstance(class_lookup.VisitNamedType(node), pytd.FunctionType):
        serializable_ast = serializable_ast.Replace(function_type_nodes=None)
        break
    except KeyError as e:
      raise UnrestorableDependencyError(
          "Unresolved class: %r." % utils.message(e)) from e
  if (serializable_ast.class_type_nodes is None or
      serializable_ast.function_type_nodes is None):
    try:
      raw_ast = raw_ast.Visit(class_lookup)
    except KeyError as e:
      raise UnrestorableDependencyError(
          "Unresolved class: %r." % utils.message(e)) from e
  serializable_ast = serializable_ast.Replace(ast=raw_ast)
  return serializable_ast


def FillLocalReferences(serializable_ast, module_map):
  """Fill in local references."""
  local_filler = visitors.FillInLocalPointers(module_map)
  if (serializable_ast.class_type_nodes is None or
      serializable_ast.function_type_nodes is None):
    serializable_ast.ast.Visit(local_filler)
    return serializable_ast.Replace(
        class_type_nodes=None, function_type_nodes=None)
  else:
    for node in serializable_ast.class_type_nodes:
      local_filler.EnterClassType(node)
      if node.cls is None:
        raise AssertionError("This should not happen: %s" % str(node))
    for node in serializable_ast.function_type_nodes:
      local_filler.EnterFunctionType(node)
      if node.function is None:
        raise AssertionError("This should not happen: %s" % str(node))
    return serializable_ast


def PrepareForExport(module_name, ast, loader):
  """Prepare an ast as if it was parsed and loaded.

  External dependencies will not be resolved, as the ast generated by this
  method is supposed to be exported.

  Args:
    module_name: The module_name as a string for the returned ast.
    ast: pytd.TypeDeclUnit, is only used if src is None.
    loader: A load_pytd.Loader instance.

  Returns:
    A pytd.TypeDeclUnit representing the supplied AST as it would look after
    being written to a file and parsed.
  """
  # This is a workaround for functionality which crept into places it doesn't
  # belong. Ideally this would call some transformation Visitors on ast to
  # transform it into the same ast we get after parsing and loading (compare
  # load_pytd.Loader.load_file). Unfortunately parsing has some special cases,
  # e.g. '__init__' return type and '__new__' being a 'staticmethod', which
  # need to be moved to visitors before we can do this. Printing an ast also
  # applies transformations,
  # e.g. visitors.PrintVisitor._FormatContainerContents, which need to move to
  # their own visitors so they can be applied without printing.
  src = pytd_utils.Print(ast)
  ast = parser.parse_string(src=src, name=module_name,
                            python_version=loader.python_version)
  ast = ast.Visit(visitors.LookupBuiltins(loader.builtins, full_names=False))
  ast = ast.Visit(visitors.ExpandCompatibleBuiltins(loader.builtins))
  ast = ast.Visit(visitors.LookupLocalTypes())
  ast = ast.Visit(visitors.AdjustTypeParameters())
  ast = ast.Visit(visitors.NamedTypeToClassType())
  ast = ast.Visit(visitors.FillInLocalPointers({"": ast, module_name: ast}))
  ast = ast.Visit(visitors.ClassTypeToLateType(
      ignore=[module_name + ".", "__builtin__.", "typing."]))
  return ast
