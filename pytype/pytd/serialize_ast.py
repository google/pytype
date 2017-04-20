"""Converts pyi files to pickled asts and saves them to disk.

Used to speed up module importing. This is done by loading the ast and
serializing it to disk. Further users only need to read the serialized data from
disk, which is faster to digest than a pyi file.
"""
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import builtins as pytd_builtins
from pytype.pytd.parse import visitors


class UnrestorableDependencyError(Exception):
  """If a dependency can't be restored in the current state."""

  def __init__(self, error_msg):
    super(UnrestorableDependencyError, self).__init__(error_msg)


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


class RenameModuleVisitor(visitors.Visitor):
  """Renames a TypeDeclUnit."""

  def __init__(self, old_module_name, new_module_name):
    """Constructor.

    Args:
      old_module_name: The old name of the module as a string,
        e.g. "foo.bar.module1"
      new_module_name: The new name of the module as a string,
        e.g. "barfoo.module2"

    Raises:
      ValueError: If the old_module name is an empty string.
    """
    super(RenameModuleVisitor, self).__init__()
    if not old_module_name:
      raise ValueError("old_module_name must be a non empty string.")
    self._old = old_module_name
    self._new = new_module_name

  def _MaybeNewName(self, name):
    """Decides if a name should be replaced.

    Args:
      name: A name for which a prefix should be changed.

    Returns:
      If name is local to the module described by old_module_name the
      old_module_part will be replaced by new_module_name and returned,
      otherwise node.name will be returned.
    """
    if name.startswith(self._old):
      return name.replace(self._old, self._new, 1)
    else:
      return name

  def _ReplaceModuleName(self, node):
    new_name = self._MaybeNewName(node.name)
    if new_name != node.name:
      return node.Replace(name=new_name)
    else:
      return node

  def VisitClassType(self, node):
    new_name = self._MaybeNewName(node.name)
    if new_name != node.name:
      return pytd.ClassType(new_name, node.cls)
    else:
      return node

  def VisitTypeDeclUnit(self, node):
    return node.Replace(name=self._new)

  def VisitTypeParameter(self, node):
    new_scope = self._MaybeNewName(node.scope)
    if new_scope != node.scope:
      return node.Replace(scope=new_scope)
    return node

  VisitConstant = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitAlias = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitClass = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitFunction = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitExternalFunction = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitStrictType = _ReplaceModuleName  # pylint: disable=invalid-name
  VisitNamedType = _ReplaceModuleName  # pylint: disable=invalid-name


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

  utils.SavePickle(serializable_ast, filename)
  return True


def EnsureAstName(ast, module_name):
  """Rename the serializable_ast if the name is different from module_name.

  Args:
    ast: An instance of SerializableAst. The attributes of this instance will be
      changed depending on ast.name and module_name.
    module_name: The name under which ast.ast should be loaded.

  Returns:
    None, the attributes of ast are modified.
  """
  # The most likely case is module_name==raw_ast.name .
  raw_ast = ast.ast

  # module_name is the name from this run, raw_ast.name is the guessed name from
  # when the ast has been pickled.
  if module_name != raw_ast.name:
    ast.ast = raw_ast.Visit(RenameModuleVisitor(raw_ast.name, module_name))
    # The ast.modified_class_types index is no longer valid, as
    # RenameModuleVisitor will have created a new AST.
    ast.modified_class_types = None


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
  raw_ast = serializable_ast.ast
  class_types = serializable_ast.modified_class_types

  module_map[raw_ast.name] = raw_ast
  module_class_filler = visitors.FillInModuleClasses(module_map)

  if class_types is not None:
    # We know all the class_types and can directly iterate over them, saving one
    # AST iteration.
    for modified_class_type in class_types:
      module_class_filler.EnterClassType(modified_class_type)
      if not modified_class_type.cls:
        raise UnrestorableDependencyError(
            "Unresolved class: %r." % modified_class_type.name)
  else:
    raw_ast = raw_ast.Visit(module_class_filler)
    try:
      raw_ast.Visit(visitors.VerifyLookup())
    except ValueError as e:
      raise UnrestorableDependencyError(e.message)

  return raw_ast


def PrepareForExport(module_name, python_version, ast):
  """Prepare an ast as if it was parsed and loaded.

  External dependencies will not be resolved, as the ast generated by this
  method is supposed to be exported.

  Args:
    module_name: The module_name as a string for the returned ast.
    python_version: A tuple of (major, minor) python version as string
      (see config.python_version).
    ast: pytd.TypeDeclUnit, is only used if src is None.

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
  src = utils.Print(ast)
  ast = pytd_builtins.ParsePyTD(src=src, module=module_name,
                                python_version=python_version)
  builtins, _ = pytd_builtins.GetBuiltinsAndTyping()
  ast = ast.Visit(visitors.LookupBuiltins(builtins, full_names=False))
  ast = ast.Visit(visitors.ExpandCompatibleBuiltins(builtins))
  ast = ast.Visit(visitors.LookupLocalTypes())
  ast = ast.Visit(visitors.AdjustTypeParameters())
  ast = ast.Visit(visitors.NamedTypeToClassType())
  ast = ast.Visit(visitors.FillInModuleClasses({"": ast, module_name: ast}))
  return ast
