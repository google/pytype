"""Common methods for tests of analyze.py."""

import contextlib
import logging
import sys
import textwrap
from typing import Tuple

from pytype import analyze
from pytype import config
from pytype import load_pytd
from pytype import module_utils
from pytype.directors import directors
from pytype.imports import pickle_utils
from pytype.platform_utils import path_utils
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.tests import test_utils

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


# For ease of importing, re-export some googletest methods. Tweak the names to
# keep the linter happy.
skip = unittest.skip
skip_if = unittest.skipIf
main = unittest.main


def _MatchLoaderConfig(options, loader):
  """Match the |options| with the configuration of |loader|."""
  if not loader:
    return False
  assert isinstance(loader, load_pytd.Loader)
  if (options.use_pickled_files !=
      isinstance(loader, load_pytd.PickledPyiLoader)):
    return False
  return options == loader.options


def _Format(code):
  # Removes the leading newline introduced by writing, e.g.,
  # self.Check("""
  #   code
  # """)
  if code.startswith("\n"):
    code = code[1:]
  return textwrap.dedent(code)


class UnitTest(unittest.TestCase):
  """Base class for tests that specify a target Python version."""

  python_version = sys.version_info[:2]


class BaseTest(unittest.TestCase):
  """Base class for implementing tests that check PyTD output."""

  _loader: load_pytd.Loader
  python_version: Tuple[int, int] = sys.version_info[:2]

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    # We use class-wide loader to avoid creating a new loader for every test
    # method if not required.
    cls._loader = None

    def t(name):  # pylint: disable=invalid-name
      return pytd.ClassType("builtins." + name)
    cls.bool = t("bool")
    cls.dict = t("dict")
    cls.float = t("float")
    cls.complex = t("complex")
    cls.int = t("int")
    cls.list = t("list")
    cls.none_type = t("NoneType")
    cls.object = t("object")
    cls.set = t("set")
    cls.frozenset = t("frozenset")
    cls.str = t("str")
    cls.bytearray = t("bytearray")
    cls.tuple = t("tuple")
    cls.unicode = t("unicode")
    cls.generator = t("generator")
    cls.function = pytd.ClassType("typing.Callable")
    cls.anything = pytd.AnythingType()
    cls.nothing = pytd.NothingType()
    cls.module = t("module")
    cls.file = t("file")

    # The various union types use pytd_utils.CanonicalOrdering()'s ordering:
    cls.intorstr = pytd.UnionType((cls.int, cls.str))
    cls.strorunicode = pytd.UnionType((cls.str, cls.unicode))
    cls.intorfloat = pytd.UnionType((cls.float, cls.int))
    cls.intorfloatorstr = pytd.UnionType((cls.float, cls.int, cls.str))
    cls.complexorstr = pytd.UnionType((cls.complex, cls.str))
    cls.intorfloatorcomplex = pytd.UnionType(
        (cls.int, cls.float, cls.complex))
    cls.int_tuple = pytd.GenericType(cls.tuple, (cls.int,))
    cls.nothing_tuple = pytd.TupleType(cls.tuple, ())
    cls.intorfloat_tuple = pytd.GenericType(cls.tuple, (cls.intorfloat,))
    cls.int_set = pytd.GenericType(cls.set, (cls.int,))
    cls.intorfloat_set = pytd.GenericType(cls.set, (cls.intorfloat,))
    cls.unknown_frozenset = pytd.GenericType(cls.frozenset, (cls.anything,))
    cls.float_frozenset = pytd.GenericType(cls.frozenset, (cls.float,))
    cls.empty_frozenset = pytd.GenericType(cls.frozenset, (cls.nothing,))
    cls.int_list = pytd.GenericType(cls.list, (cls.int,))
    cls.str_list = pytd.GenericType(cls.list, (cls.str,))
    cls.intorfloat_list = pytd.GenericType(cls.list, (cls.intorfloat,))
    cls.intorstr_list = pytd.GenericType(cls.list, (cls.intorstr,))
    cls.anything_list = pytd.GenericType(cls.list, (cls.anything,))
    cls.nothing_list = pytd.GenericType(cls.list, (cls.nothing,))
    cls.int_int_dict = pytd.GenericType(cls.dict, (cls.int, cls.int))
    cls.int_str_dict = pytd.GenericType(cls.dict, (cls.int, cls.str))
    cls.str_int_dict = pytd.GenericType(cls.dict, (cls.str, cls.int))
    cls.nothing_nothing_dict = pytd.GenericType(cls.dict,
                                                (cls.nothing, cls.nothing))
    cls.make_tuple = lambda self, *args: pytd.TupleType(cls.tuple, tuple(args))

  def setUp(self):
    super().setUp()
    self.options = config.Options.create(
        python_version=self.python_version,
        always_use_return_annotations=True,
        enable_cached_property=True,
        overriding_default_value_checks=True,
        overriding_parameter_count_checks=True,
        overriding_parameter_name_checks=True,
        overriding_return_type_checks=True,
        strict_parameter_checks=True,
        strict_primitive_comparisons=True,
        use_enum_overlay=True)

  @property
  def loader(self):
    if not _MatchLoaderConfig(self.options, self._loader):
      # Create a new loader only if the configuration in the current options
      # does not match the configuration in the current loader.
      self._loader = load_pytd.create_loader(self.options)
    return self._loader

  def ConfigureOptions(self, **kwargs):
    assert "python_version" not in kwargs, (
        "Individual tests cannot set the python_version of the config options.")
    self.options.tweak(**kwargs)

  def _GetPythonpathArgs(self, pythonpath, imports_map):
    """Gets values for --pythonpath and --imports_map."""
    if pythonpath:
      pythonpath_arg = pythonpath
      imports_map_arg = imports_map
    elif imports_map:
      pythonpath_arg = [""]
      imports_map_arg = imports_map
    else:
      pythonpath_arg = self.options.pythonpath
      imports_map_arg = self.options.imports_map
    return {"pythonpath": pythonpath_arg, "imports_map": imports_map_arg}

  # For historical reasons (byterun), this method name is snakecase:
  # pylint: disable=invalid-name
  def Check(self, code, pythonpath=(), skip_repeat_calls=True,
            report_errors=True, filename=None, quick=False, imports_map=None,
            **kwargs):
    """Run an inference smoke test for the given code."""
    self.ConfigureOptions(
        skip_repeat_calls=skip_repeat_calls, quick=quick,
        **self._GetPythonpathArgs(pythonpath, imports_map))
    try:
      src = _Format(code)
      if test_utils.ErrorMatcher(code).expected:
        self.fail("Cannot assert errors with Check(); use CheckWithErrors()")
      ret = analyze.check_types(
          src, filename, loader=self.loader, options=self.options, **kwargs)
      errorlog = ret.errorlog
    except directors.SkipFileError:
      errorlog = None
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail(f"Checker found {len(errorlog)} errors:\n{errorlog}")

  def assertNoCrash(self, method, code, **kwargs):
    method(code, report_errors=False, **kwargs)

  def _SetUpErrorHandling(self, code, pythonpath, analyze_annotated, quick,
                          imports_map):
    code = _Format(code)
    self.ConfigureOptions(
        analyze_annotated=analyze_annotated, quick=quick,
        **self._GetPythonpathArgs(pythonpath, imports_map))
    return {"src": code, "options": self.options, "loader": self.loader}

  def InferWithErrors(self, code, deep=True, pythonpath=(), module_name=None,
                      analyze_annotated=True, quick=False, imports_map=None,
                      **kwargs):
    """Runs inference on code expected to have type errors."""
    kwargs.update(self._SetUpErrorHandling(
        code, pythonpath, analyze_annotated, quick, imports_map))
    self.ConfigureOptions(module_name=module_name)
    ret = analyze.infer_types(deep=deep, **kwargs)
    unit = ret.ast
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(unit, ret.builtins, lossy=False, use_abcs=False,
                             max_union=7, remove_mutable=False)
    errorlog = ret.errorlog
    src = kwargs["src"]
    matcher = test_utils.ErrorMatcher(src)
    matcher.assert_errors_match_expected(errorlog)
    return pytd_utils.CanonicalOrdering(unit), matcher

  def CheckWithErrors(self, code, deep=True, pythonpath=(),
                      analyze_annotated=True, quick=False, imports_map=None,
                      **kwargs):
    """Check and match errors."""
    kwargs.update(self._SetUpErrorHandling(
        code, pythonpath, analyze_annotated, quick, imports_map))
    ret = analyze.check_types(filename="<inline>", deep=deep, **kwargs)
    errorlog = ret.errorlog
    src = kwargs["src"]
    matcher = test_utils.ErrorMatcher(src)
    matcher.assert_errors_match_expected(errorlog)
    return matcher

  def InferFromFile(self, filename, pythonpath):
    """Runs inference on the contents of a file."""
    with open(filename) as fi:
      code = fi.read()
      if test_utils.ErrorMatcher(code).expected:
        self.fail(
            "Cannot assert errors with InferFromFile(); use InferWithErrors()")
      self.ConfigureOptions(
          module_name=module_utils.get_module_name(filename, pythonpath),
          pythonpath=pythonpath)
      ret = analyze.infer_types(code, options=self.options, loader=self.loader,
                                filename=filename)
      unit = ret.ast
      unit.Visit(visitors.VerifyVisitor())
      return pytd_utils.CanonicalOrdering(unit)

  @classmethod
  def SignatureHasReturnType(cls, sig, return_type):
    for desired_type in pytd_utils.UnpackUnion(return_type):
      if desired_type == return_type:
        return True
      elif isinstance(sig.return_type, pytd.UnionType):
        return desired_type in sig.return_type.type_list
      else:
        return False

  @classmethod
  def HasSignature(cls, func, parameter_types, return_type):
    for sig in func.signatures:
      if (parameter_types == tuple(p.type for p in sig.params) and
          cls.SignatureHasReturnType(sig, return_type)):
        return True
    return False

  @classmethod
  def HasExactSignature(cls, func, parameter_types, return_type):
    for sig in func.signatures:
      if (parameter_types == tuple(p.type for p in sig.params) and
          return_type == sig.return_type):
        return True
    return False

  @classmethod
  def PrintSignature(cls, parameter_types, return_type):
    return "({}) -> {}".format(
        ", ".join(pytd_utils.Print(t) for t in parameter_types),
        pytd_utils.Print(return_type))

  def assertHasOnlySignatures(self, func, *sigs):
    """Asserts that the function has the given signatures and no others."""
    self.assertIsInstance(func, pytd.Function)
    for parameter_types, return_type in sigs:
      if not self.HasExactSignature(func, parameter_types, return_type):
        self.fail("Could not find signature: {name}{sig} in {func}".
                  format(name=func.name,
                         sig=self.PrintSignature(parameter_types, return_type),
                         func=pytd_utils.Print(func)))
    msg = ("{func} has the wrong number of signatures ({has}), "
           "expected {expect}".format(
               func=func, has=len(func.signatures), expect=len(sigs)))
    self.assertEqual(len(func.signatures), len(sigs), msg)

  def assertHasSignature(self, func, parameter_types, return_type):
    if not self.HasSignature(func, parameter_types, return_type):
      self.fail("Could not find signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type),
          pytd_utils.Print(func)))

  def assertNotHasSignature(self, func, parameter_types, return_type):
    if self.HasSignature(func, parameter_types, return_type):
      self.fail("Found signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type),
          pytd_utils.Print(func)))

  def assertTypeEquals(self, t1, t2):
    self.assertEqual(t1, t2,
                     f"Type {pytd_utils.Print(t1)!r} != "
                     f"{pytd_utils.Print(t2)!r}")

  def assertOnlyHasReturnType(self, func, t):
    """Test that a given return type is the only one."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    self.assertEqual(t, ret,
                     "Return type {!r} != {!r}".format(pytd_utils.Print(t),
                                                       pytd_utils.Print(ret)))

  def assertHasReturnType(self, func, t):
    """Test that a given return type is present. Ignore extras."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    if isinstance(ret, pytd.UnionType):
      self.assertIn(t, ret.type_list,
                    "Return type {!r} not found in {!r}".format(
                        pytd_utils.Print(t), pytd_utils.Print(ret)))
    else:
      self.assertEqual(t, ret,
                       "Return type {!r} != {!r}".format(pytd_utils.Print(ret),
                                                         pytd_utils.Print(t)))

  def assertHasAllReturnTypes(self, func, types):
    """Test that all given return types are present. Ignore extras."""
    for t in types:
      self.assertHasReturnType(func, t)

  def assertIsIdentity(self, func):
    """Tests whether a given function is equivalent to the identity function."""
    self.assertGreaterEqual(len(func.signatures), 1)
    for sig in func.signatures:
      self.assertEqual(len(sig.params), 1)
      param1, = sig.params
      self.assertEqual(param1.type, sig.return_type,
                       f"Not identity: {pytd_utils.Print(func)!r}")

  def assertErrorRegexes(self, matcher, expected_errors):
    matcher.assert_error_regexes(expected_errors)

  def assertErrorSequences(self, matcher, expected_errors):
    matcher.assert_error_sequences(expected_errors)

  def _PickleAst(self, ast, module_name):
    assert module_name
    ast = serialize_ast.PrepareForExport(module_name, ast, self.loader)
    return pickle_utils.StoreAst(ast)

  def _PickleSource(self, src, module_name):
    ast = serialize_ast.SourceToExportableAst(
        module_name, textwrap.dedent(src), self.loader)
    return pickle_utils.StoreAst(ast)

  def Infer(self, srccode, pythonpath=(), deep=True,
            report_errors=True, analyze_annotated=True, pickle=False,
            module_name=None, **kwargs):
    """Runs inference on srccode."""
    types, builtins_pytd = self._InferAndVerify(
        _Format(srccode), pythonpath=pythonpath, deep=deep,
        analyze_annotated=analyze_annotated, module_name=module_name,
        report_errors=report_errors, **kwargs)
    types = optimize.Optimize(types, builtins_pytd, lossy=False, use_abcs=False,
                              max_union=7, remove_mutable=False)
    types = pytd_utils.CanonicalOrdering(types)
    if pickle:
      return self._PickleAst(types, module_name)
    else:
      return types

  def _InferAndVerify(
      self, src, pythonpath, module_name, report_errors, analyze_annotated,
      imports_map=None, quick=False, **kwargs):
    """Infer types for the source code treating it as a module.

    Used by Infer().

    Args:
      src: The source code of a module. Treat it as "__main__".
      pythonpath: --pythonpath as list/tuple of string
      module_name: Name of the module we're analyzing. E.g. "foo.bar.mymodule".
      report_errors: Whether to fail if the type inferencer reports any errors
        in the program.
      analyze_annotated: Whether to analyze functions with return annotations.
      imports_map: --imports_info data
      quick: Try to run faster, by avoiding costly computations.
      **kwargs: Keyword parameters to pass through to the type inferencer.

    Raises:
      AssertionError: If report_errors is True and we found errors.
    Returns:
      A pytd.TypeDeclUnit
    """
    self.ConfigureOptions(
        module_name=module_name, quick=quick, use_pickled_files=True,
        analyze_annotated=analyze_annotated,
        **self._GetPythonpathArgs(pythonpath, imports_map))
    if test_utils.ErrorMatcher(src).expected:
      self.fail("Cannot assert errors with Infer(); use InferWithErrors()")
    ret = analyze.infer_types(
        src, options=self.options, loader=self.loader, **kwargs)
    errorlog = ret.errorlog
    unit = ret.ast
    unit.Visit(visitors.VerifyVisitor())
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail(
          f"Inferencer found {len(errorlog)} errors:\n{errorlog}")
    return unit, ret.builtins

  def assertTypesMatchPytd(self, ty, pytd_src):
    """Parses pytd_src and compares with ty."""
    pytd_tree = parser.parse_string(
        textwrap.dedent(pytd_src),
        options=parser.PyiOptions(python_version=self.python_version))
    pytd_tree = pytd_tree.Visit(visitors.LookupBuiltins(
        self.loader.builtins, full_names=False))
    pytd_tree = pytd_tree.Visit(visitors.LookupLocalTypes())
    pytd_tree = pytd_tree.Visit(
        visitors.ClassTypeToNamedType())
    pytd_tree = pytd_tree.Visit(visitors.CanonicalOrderingVisitor())
    pytd_tree.Visit(visitors.VerifyVisitor())
    ty = ty.Visit(visitors.ClassTypeToNamedType())
    ty = ty.Visit(visitors.AdjustSelf())
    ty = ty.Visit(visitors.CanonicalOrderingVisitor())
    ty.Visit(visitors.VerifyVisitor())

    ty_src = pytd_utils.Print(ty) + "\n"
    pytd_tree_src = pytd_utils.Print(pytd_tree) + "\n"

    log.info("========== result   ==========")
    _LogLines(log.info, ty_src)
    log.info("========== expected ==========")
    _LogLines(log.info, pytd_tree_src)
    log.info("==============================")

    # In the diff output, mark expected with "-" and actual with "+".
    # (In other words, display a change from "working" to "broken")
    self.assertMultiLineEqual(pytd_tree_src, ty_src)

  @contextlib.contextmanager
  def DepTree(self, deps):
    """Creates a tree of .pyi deps."""
    old_pythonpath = self.options.pythonpath
    old_imports_map = self.options.imports_map
    try:
      with test_utils.Tempdir() as d:
        self.ConfigureOptions(pythonpath=[""], imports_map={})
        for dep in deps:
          if len(dep) == 3:
            path, contents, opts = dep
          else:
            path, contents = dep
            opts = {}
          base, ext = path_utils.splitext(path)
          pickle = opts.get("pickle", False)
          new_path = base + (".pickled" if pickle else ".pyi")
          if ext == ".pyi":
            if pickle:
              contents = self._PickleSource(contents, base)
            filepath = d.create_file(new_path, contents)
          elif ext == ".py":
            pyi = self.Infer(contents, module_name=base, **opts)
            if not pickle:
              pyi = pytd_utils.Print(pyi)
            filepath = d.create_file(new_path, pyi)
          else:
            raise ValueError(f"Unrecognised dependency type: {path}")
          self.options.imports_map[base] = filepath
        yield d
    finally:
      self.ConfigureOptions(pythonpath=old_pythonpath,
                            imports_map=old_imports_map)


def _PrintErrorDebug(descr, value):
  log.error("=============== %s ===========", descr)
  _LogLines(log.error, value)
  log.error("=========== end %s ===========", descr)


def _LogLines(log_cmd, lines):
  for l in lines.split("\n"):
    log_cmd("%s", l)
