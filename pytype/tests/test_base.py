"""Common methods for tests of analyze.py."""

import logging
import sys
import textwrap
from typing import Tuple

from pytype import analyze
from pytype import config
from pytype import directors
from pytype import load_pytd
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.tests import test_utils
import six

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


# For ease of importing, re-export unittest.skip*. Tweak the name to keep the
# linter happy.
skip = unittest.skip
skip_if = unittest.skipIf


def _MatchLoaderConfig(options, loader):
  """Match the |options| with the configuration of |loader|."""
  if not loader:
    return False
  assert isinstance(loader, load_pytd.Loader)
  if (options.use_pickled_files !=
      isinstance(loader, load_pytd.PickledPyiLoader)):
    return False
  for loader_attr, opt in load_pytd.LOADER_ATTR_TO_CONFIG_OPTION_MAP.items():
    if getattr(options, opt) != getattr(loader, loader_attr):
      return False
  return True


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

  def setUp(self):
    super().setUp()
    self.options = config.Options.create(python_version=self.python_version,
                                         attribute_variable_annotations=True,
                                         bind_properties=True,
                                         chex_overlay=True,
                                         preserve_union_macros=True,
                                         use_enum_overlay=True,
                                         enforce_noniterable_strings=True)

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

  # For historical reasons (byterun), this method name is snakecase:
  # pylint: disable=invalid-name
  def Check(self, code, pythonpath=(), skip_repeat_calls=True,
            report_errors=True, filename=None, quick=False, imports_map=None,
            **kwargs):
    """Run an inference smoke test for the given code."""
    self.ConfigureOptions(
        skip_repeat_calls=skip_repeat_calls,
        pythonpath=[""] if (not pythonpath and imports_map) else pythonpath,
        quick=quick, imports_map=imports_map)
    try:
      if six.PY3:
        src = _Format(code)
      else:
        src = _Format(code.decode("utf-8"))
      errorlog = test_utils.TestErrorLog(code)
      if errorlog.expected:
        self.fail("Cannot assert errors with Check(); use CheckWithErrors()")
      analyze.check_types(
          src, filename, loader=self.loader,
          errorlog=errorlog, options=self.options, **kwargs)
    except directors.SkipFileError:
      pass
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail("Checker found {} errors:\n{}".format(len(errorlog), errorlog))

  def assertNoCrash(self, method, code, **kwargs):
    method(code, report_errors=False, **kwargs)

  def _SetUpErrorHandling(self, code, pythonpath, analyze_annotated, quick,
                          imports_map):
    code = _Format(code)
    errorlog = test_utils.TestErrorLog(code)
    self.ConfigureOptions(
        pythonpath=[""] if (not pythonpath and imports_map) else pythonpath,
        analyze_annotated=analyze_annotated, quick=quick,
        imports_map=imports_map)
    return {"src": code, "errorlog": errorlog, "options": self.options,
            "loader": self.loader}

  def InferWithErrors(self, code, deep=True, pythonpath=(), module_name=None,
                      analyze_annotated=True, quick=False, imports_map=None,
                      **kwargs):
    kwargs.update(self._SetUpErrorHandling(
        code, pythonpath, analyze_annotated, quick, imports_map))
    self.ConfigureOptions(module_name=module_name)
    unit, builtins_pytd = analyze.infer_types(deep=deep, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(unit, builtins_pytd, lossy=False, use_abcs=False,
                             max_union=7, remove_mutable=False)
    errorlog = kwargs["errorlog"]
    errorlog.assert_errors_match_expected()
    return pytd_utils.CanonicalOrdering(unit), errorlog

  def CheckWithErrors(self, code, deep=True, pythonpath=(),
                      analyze_annotated=True, quick=False, imports_map=None,
                      **kwargs):
    kwargs.update(self._SetUpErrorHandling(
        code, pythonpath, analyze_annotated, quick, imports_map))
    analyze.check_types(filename="<inline>", deep=deep, **kwargs)
    errorlog = kwargs["errorlog"]
    errorlog.assert_errors_match_expected()
    return errorlog

  def InferFromFile(self, filename, pythonpath):
    with open(filename, "r") as fi:
      code = fi.read()
      errorlog = test_utils.TestErrorLog(code)
      if errorlog.expected:
        self.fail(
            "Cannot assert errors with InferFromFile(); use InferWithErrors()")
      self.ConfigureOptions(
          module_name=load_pytd.get_module_name(filename, pythonpath),
          pythonpath=pythonpath)
      unit, _ = analyze.infer_types(code, errorlog, self.options,
                                    loader=self.loader, filename=filename)
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
    return "(%s) -> %s" % (
        ", ".join(pytd_utils.Print(t) for t in parameter_types),
        pytd_utils.Print(return_type))

  def assertHasOnlySignatures(self, func, *sigs):
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
                     "Type %r != %r" % (pytd_utils.Print(t1),
                                        pytd_utils.Print(t2)))

  def assertOnlyHasReturnType(self, func, t):
    """Test that a given return type is the only one."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    self.assertEqual(t, ret,
                     "Return type %r != %r" % (pytd_utils.Print(t),
                                               pytd_utils.Print(ret)))

  def assertHasReturnType(self, func, t):
    """Test that a given return type is present. Ignore extras."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    if isinstance(ret, pytd.UnionType):
      self.assertIn(t, ret.type_list,
                    "Return type %r not found in %r" % (pytd_utils.Print(t),
                                                        pytd_utils.Print(ret)))
    else:
      self.assertEqual(t, ret,
                       "Return type %r != %r" % (pytd_utils.Print(ret),
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
                       "Not identity: %r" % pytd_utils.Print(func))

  def assertErrorRegexes(self, errorlog, expected_errors):
    errorlog.assert_error_regexes(expected_errors)

  def _Pickle(self, ast, module_name):
    assert module_name
    ast = serialize_ast.PrepareForExport(module_name, ast, self.loader)
    return serialize_ast.StoreAst(ast)

  def Infer(self, srccode, pythonpath=(), deep=True,
            report_errors=True, analyze_annotated=True, pickle=False,
            module_name=None, **kwargs):
    types, builtins_pytd = self._InferAndVerify(
        _Format(srccode), pythonpath=pythonpath, deep=deep,
        analyze_annotated=analyze_annotated, module_name=module_name,
        report_errors=report_errors, **kwargs)
    types = optimize.Optimize(types, builtins_pytd, lossy=False, use_abcs=False,
                              max_union=7, remove_mutable=False)
    types = pytd_utils.CanonicalOrdering(types)
    if pickle:
      return self._Pickle(types, module_name)
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
        pythonpath=[""] if (not pythonpath and imports_map) else pythonpath,
        imports_map=imports_map, analyze_annotated=analyze_annotated)
    errorlog = test_utils.TestErrorLog(src)
    if errorlog.expected:
      self.fail("Cannot assert errors with Infer(); use InferWithErrors()")
    unit, builtins_pytd = analyze.infer_types(
        src, errorlog, self.options, loader=self.loader, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail(
          "Inferencer found {} errors:\n{}".format(len(errorlog), errorlog))
    return unit, builtins_pytd

  def assertTypesMatchPytd(self, ty, pytd_src):
    """Parses pytd_src and compares with ty."""
    pytd_tree = parser.parse_string(
        textwrap.dedent(pytd_src), python_version=self.python_version)
    pytd_tree = pytd_tree.Visit(visitors.LookupBuiltins(
        self.loader.builtins, full_names=False))
    pytd_tree = pytd_tree.Visit(visitors.LookupLocalTypes())
    pytd_tree = pytd_tree.Visit(
        visitors.ClassTypeToNamedType())
    pytd_tree = pytd_tree.Visit(
        visitors.CanonicalOrderingVisitor(sort_signatures=True))
    pytd_tree.Visit(visitors.VerifyVisitor())
    ty = ty.Visit(visitors.ClassTypeToNamedType())
    ty = ty.Visit(visitors.AdjustSelf())
    ty = ty.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
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


# TODO(rechen): Get rid of these subclasses.
class TargetIndependentTest(BaseTest):
  """Class for tests which are independent of the target Python version.

  Test methods in subclasses will operate on Python code which does not use any
  feature specific to a Python version, including type annotations.
  """


class TargetPython27FeatureTest(BaseTest):
  """Class for tests which depend on a Python 2.7 feature.

  Test methods in subclasses will test Pytype on a Python 2.7 feature.
  """


class TargetPython3BasicTest(BaseTest):
  """Class for tests using type annotations as the only Python 3 feature.

  Test methods in subclasses will test Pytype on Python code stubs which use
  type annotations as the only Python 3 feature.
  """


class TargetPython3FeatureTest(BaseTest):
  """Class for tests which depend on a Python 3 feature beyond type annotations.

  Test methods in subclasses will test Pytype on a Python 3 feature.
  """


def _PrintErrorDebug(descr, value):
  log.error("=============== %s ===========", descr)
  _LogLines(log.error, value)
  log.error("=========== end %s ===========", descr)


def _LogLines(log_cmd, lines):
  for l in lines.split("\n"):
    log_cmd("%s", l)


# TODO(rechen): Get rid of this method.
def main(toplevels, is_main_module=True):
  del toplevels  # unused
  if is_main_module:
    unittest.main()
