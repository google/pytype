"""Common methods for tests of analyze.py."""

import collections
import logging
import re
import sys
import textwrap


from pytype import analyze
from pytype import compat
from pytype import config
from pytype import debug
from pytype import directors
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


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


class BaseTest(unittest.TestCase):
  """Base class for implementing tests that check PyTD output."""

  PYTHON_VERSION = (2, 7)  # can be overwritten by subclasses

  @classmethod
  def setUpClass(cls):
    # We use class-wide loader to avoid creating a new loader for every test
    # method if not required.
    cls._loader = None

    def t(name):  # pylint: disable=invalid-name
      return pytd.ClassType("__builtin__." + name)
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
    cls.nothing_tuple = pytd.GenericType(cls.tuple, (cls.nothing,))
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
    self.options = config.Options.create(
        python_version=self.PYTHON_VERSION,
        python_exe=utils.get_python_exe(self.PYTHON_VERSION))

  @property
  def loader(self):
    if not _MatchLoaderConfig(self.options, self._loader):
      # Create a new loader only if the configuration in the current options
      # does not match the configuration in the current loader.
      self._loader = load_pytd.create_loader(self.options)
    return self._loader

  def ConfigureOptions(self, **kwargs):
    self.options.tweak(**kwargs)
    if self.options.python_version is None:
      self.options.python_version = self.PYTHON_VERSION
    self.options.tweak(
        python_exe=utils.get_python_exe(self.options.python_version))

  # For historical reasons (byterun), this method name is snakecase:
  # TODO(kramm): Rename this function.
  # pylint: disable=invalid-name
  def Check(self, code, pythonpath=(), skip_repeat_calls=True,
            report_errors=True, filename=None, python_version=None, **kwargs):
    """Run an inference smoke test for the given code."""
    self.ConfigureOptions(skip_repeat_calls=skip_repeat_calls,
                          pythonpath=pythonpath, python_version=python_version)
    errorlog = errors.ErrorLog()
    try:
      analyze.check_types(
          textwrap.dedent(code), filename, loader=self.loader,
          errorlog=errorlog, options=self.options, **kwargs)
    except directors.SkipFile:
      pass
    if report_errors and len(errorlog):
      errorlog.print_to_stderr()
      self.fail("Checker found %d errors" % len(errorlog))

  def assertNoCrash(self, method, code, **kwargs):
    method(code, report_errors=False, **kwargs)

  def _SetUpErrorHandling(self, code, pythonpath, python_version):
    code = textwrap.dedent(code)
    errorlog = errors.ErrorLog()
    self.ConfigureOptions(pythonpath=pythonpath, python_version=python_version)
    return {"src": code, "errorlog": errorlog, "options": self.options,
            "loader": self.loader}

  def InferWithErrors(self, code, deep=True, pythonpath=(), python_version=None,
                      **kwargs):
    kwargs.update(self._SetUpErrorHandling(code, pythonpath, python_version))
    unit, builtins_pytd = analyze.infer_types(
        deep=deep, analyze_annotated=True, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(unit, builtins_pytd, lossy=False, use_abcs=False,
                             max_union=7, remove_mutable=False)
    return pytd_utils.CanonicalOrdering(unit), kwargs["errorlog"]

  def CheckWithErrors(self, code, deep=True, pythonpath=(), python_version=None,
                      **kwargs):
    kwargs.update(self._SetUpErrorHandling(code, pythonpath, python_version))
    analyze.check_types(filename="<inline>", deep=deep, **kwargs)
    return kwargs["errorlog"]

  def InferFromFile(self, filename, pythonpath, python_version=None):
    with open(filename, "r") as fi:
      code = fi.read()
      errorlog = errors.ErrorLog()
      self.ConfigureOptions(
          module_name=load_pytd.get_module_name(filename, pythonpath),
          pythonpath=pythonpath, python_version=python_version)
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
    return "(%s) -> %s" % (", ".join(pytd.Print(t) for t in parameter_types),
                           pytd.Print(return_type))

  def assertHasOnlySignatures(self, func, *sigs):
    self.assertIsInstance(func, pytd.Function)
    for parameter_types, return_type in sigs:
      if not self.HasExactSignature(func, parameter_types, return_type):
        self.fail("Could not find signature: {name}{sig} in {func}".
                  format(name=func.name,
                         sig=self.PrintSignature(parameter_types, return_type),
                         func=pytd.Print(func)))
    self.assertEqual(len(func.signatures), len(sigs),
                     "{func} has the wrong number of signatures ({has}), "
                     "expected {expect}".
                     format(func=func,
                            has=len(func.signatures), expect=len(sigs)))

  def assertHasSignature(self, func, parameter_types, return_type):
    if not self.HasSignature(func, parameter_types, return_type):
      self.fail("Could not find signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type), pytd.Print(func)))

  def assertNotHasSignature(self, func, parameter_types, return_type):
    if self.HasSignature(func, parameter_types, return_type):
      self.fail("Found signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type), pytd.Print(func)))

  def assertTypeEquals(self, t1, t2):
    self.assertEqual(t1, t2,
                     "Type %r != %r" % (pytd.Print(t1),
                                        pytd.Print(t2)))

  def assertOnlyHasReturnType(self, func, t):
    """Test that a given return type is the only one."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    self.assertEqual(t, ret,
                     "Return type %r != %r" % (pytd.Print(t),
                                               pytd.Print(ret)))

  def assertHasReturnType(self, func, t):
    """Test that a given return type is present. Ignore extras."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    if isinstance(ret, pytd.UnionType):
      self.assertIn(t, ret.type_list,
                    "Return type %r not found in %r" % (pytd.Print(t),
                                                        pytd.Print(ret)))
    else:
      self.assertEqual(t, ret,
                       "Return type %r != %r" % (pytd.Print(ret),
                                                 pytd.Print(t)))

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
                       "Not identity: %r" % pytd.Print(func))

  def _parse_expected_error(self, pattern):
    assert 2 <= len(pattern) <= 3, (
        "Bad expected error format. Use: (<line>, <name>[, <regexp>])")
    line = pattern[0]
    name = pattern[1]
    regexp = pattern[2] if len(pattern) > 2 else ""
    return line, name, regexp

  def assertErrorLogIs(self, errorlog, expected_errors):
    expected_errors = collections.Counter(expected_errors)
    # This is O(|errorlog| * |expected_errors|), which is okay because error
    # lists in tests are short.
    for error in errorlog.unique_sorted_errors():
      almost_matches = set()
      for (pattern, count) in expected_errors.items():
        line, name, regexp = self._parse_expected_error(pattern)
        if line == error.lineno and name == error.name:
          if not regexp or re.search(regexp, error.message, flags=re.DOTALL):
            if count == 1:
              del expected_errors[pattern]
            else:
              expected_errors[pattern] -= 1
            break
          else:
            almost_matches.add(regexp)
      else:
        errorlog.print_to_stderr()
        if almost_matches:
          raise AssertionError("Bad error message: expected %r, got %r" % (
              almost_matches.pop(), error.message))
        else:
          raise AssertionError("Unexpected error:\n%s" % error)
    if expected_errors:
      errorlog.print_to_stderr()
      leftover_errors = [
          self._parse_expected_error(pattern) for pattern in expected_errors]
      raise AssertionError("Errors not found:\n" + "\n".join(
          "Line %d: %r [%s]" % (e[0], e[2], e[1]) for e in leftover_errors))

  def _Pickle(self, ast, module_name):
    assert module_name
    ast = serialize_ast.PrepareForExport(
        module_name, self.PYTHON_VERSION, ast, self.loader)
    return serialize_ast.StoreAst(ast)

  def Infer(self, srccode, pythonpath=(), deep=True,
            report_errors=True, analyze_annotated=True, pickle=False,
            module_name=None, python_version=None, **kwargs):
    types, builtins_pytd = self._InferAndVerify(
        textwrap.dedent(srccode), pythonpath=pythonpath, deep=deep,
        analyze_annotated=analyze_annotated, module_name=module_name,
        report_errors=report_errors, python_version=python_version, **kwargs)
    types = optimize.Optimize(types, builtins_pytd, lossy=False, use_abcs=False,
                              max_union=7, remove_mutable=False)
    types = pytd_utils.CanonicalOrdering(types)
    if pickle:
      return self._Pickle(types, module_name)
    else:
      return types

  def _InferAndVerify(self, src, pythonpath, module_name, report_errors,
                      python_version, imports_map=None, quick=False, **kwargs):
    """Infer types for the source code treating it as a module.

    Used by Infer().

    Args:
      src: The source code of a module. Treat it as "__main__".
      pythonpath: --pythonpath as list/tuple of string
      module_name: Name of the module we're analyzing. E.g. "foo.bar.mymodule".
      report_errors: Whether to fail if the type inferencer reports any errors
        in the program.
      python_version: The python version.
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
        imports_map=imports_map, python_version=python_version)
    errorlog = errors.ErrorLog()
    # TODO(mdemello): Setting 'quick' does not set maximum depth in infer_types.
    unit, builtins_pytd = analyze.infer_types(
        src, errorlog, self.options, loader=self.loader, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    if report_errors and len(errorlog):
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    return unit, builtins_pytd

  def assertTypesMatchPytd(self, ty, pytd_src):
    """Parses pytd_src and compares with ty."""
    pytd_tree = parser.parse_string(
        textwrap.dedent(pytd_src), python_version=self.PYTHON_VERSION)
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

    ty_src = pytd.Print(ty) + "\n"
    pytd_tree_src = pytd.Print(pytd_tree) + "\n"

    log.info("========== result   ==========")
    _LogLines(log.info, ty_src)
    log.info("========== expected ==========")
    _LogLines(log.info, pytd_tree_src)
    log.info("==============================")

    # In the diff output, mark expected with "-" and actual with "+".
    # (In other words, display a change from "working" to "broken")
    self.assertMultiLineEqual(pytd_tree_src, ty_src)

  def make_code(self, int_array, name="testcode"):
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, kwonlyargcount=0, nlocals=2, stacksize=2, flags=0,
        consts=[None, 1, 2], names=[], varnames=["x", "y"], filename="",
        name=name, firstlineno=1, lnotab=[], freevars=[], cellvars=[],
        code=compat.int_array_to_bytes(int_array),
        python_version=self.PYTHON_VERSION)


def _PrintErrorDebug(descr, value):
  log.error("=============== %s ===========", descr)
  _LogLines(log.error, value)
  log.error("=========== end %s ===========", descr)


def _LogLines(log_cmd, lines):
  for l in lines.split("\n"):
    log_cmd("%s", l)


def main(debugging=False):
  # TODO(ampere): This is just a useful hack. Should be replaced with real
  #               argument handling.
  level = logging.DEBUG if debugging or len(sys.argv) > 1 else logging.WARNING
  debug.set_logging_level(level)
  unittest.main()

if __name__ == "__main__":
  main()
