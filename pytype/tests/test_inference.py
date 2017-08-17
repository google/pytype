"""Common methods for tests of infer.py."""

import collections
import logging
import os
import re
import sys
import textwrap


from pytype import config
from pytype import debug
from pytype import errors
from pytype import infer
from pytype import load_pytd
from pytype.pyc import loadmarshal
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


class InferenceTest(unittest.TestCase):
  """Base class for implementing tests that check PyTD output."""

  PYTHON_VERSION = (2, 7)  # can be overwritten by subclasses

  # Can be overwritten by subclasses
  PYTHON_EXE = None

  def setUp(self):
    self.options = config.Options.create(python_version=self.PYTHON_VERSION,
                                         python_exe=self.PYTHON_EXE)

    def t(name):  # pylint: disable=invalid-name
      return pytd.ClassType("__builtin__." + name)
    self.bool = t("bool")
    self.dict = t("dict")
    self.float = t("float")
    self.complex = t("complex")
    self.int = t("int")
    self.list = t("list")
    self.none_type = t("NoneType")
    self.object = t("object")
    self.set = t("set")
    self.frozenset = t("frozenset")
    self.str = t("str")
    self.bytearray = t("bytearray")
    self.tuple = t("tuple")
    self.unicode = t("unicode")
    self.generator = t("generator")
    self.function = pytd.ClassType("typing.Callable")
    self.anything = pytd.AnythingType()
    self.nothing = pytd.NothingType()
    self.module = t("module")
    self.file = t("file")

    # The various union types use pytd_utils.CanonicalOrdering()'s ordering:
    self.intorstr = pytd.UnionType((self.int, self.str))
    self.strorunicode = pytd.UnionType((self.str, self.unicode))
    self.intorfloat = pytd.UnionType((self.float, self.int))
    self.intorfloatorstr = pytd.UnionType((self.float, self.int, self.str))
    self.complexorstr = pytd.UnionType((self.complex, self.str))
    self.intorfloatorcomplex = pytd.UnionType(
        (self.int, self.float, self.complex))
    self.int_tuple = pytd.GenericType(self.tuple, (self.int,))
    self.nothing_tuple = pytd.GenericType(self.tuple, (self.nothing,))
    self.intorfloat_tuple = pytd.GenericType(self.tuple, (self.intorfloat,))
    self.int_set = pytd.GenericType(self.set, (self.int,))
    self.intorfloat_set = pytd.GenericType(self.set, (self.intorfloat,))
    self.unknown_frozenset = pytd.GenericType(self.frozenset, (self.anything,))
    self.float_frozenset = pytd.GenericType(self.frozenset, (self.float,))
    self.empty_frozenset = pytd.GenericType(self.frozenset, (self.nothing,))
    self.int_list = pytd.GenericType(self.list, (self.int,))
    self.str_list = pytd.GenericType(self.list, (self.str,))
    self.intorfloat_list = pytd.GenericType(self.list, (self.intorfloat,))
    self.intorstr_list = pytd.GenericType(self.list, (self.intorstr,))
    self.anything_list = pytd.GenericType(self.list, (self.anything,))
    self.nothing_list = pytd.GenericType(self.list, (self.nothing,))
    self.int_int_dict = pytd.GenericType(self.dict, (self.int, self.int))
    self.int_str_dict = pytd.GenericType(self.dict, (self.int, self.str))
    self.str_int_dict = pytd.GenericType(self.dict, (self.str, self.int))
    self.nothing_nothing_dict = pytd.GenericType(self.dict,
                                                 (self.nothing, self.nothing))

  # For historical reasons (byterun), this method name is snakecase:
  # TODO(kramm): Rename this function.
  # pylint: disable=invalid-name
  def assertNoErrors(self, code, raises=None,
                     pythonpath=(), skip_repeat_calls=True, report_errors=True):
    """Run an inference smoke test for the given code."""
    if raises is not None:
      # TODO(kramm): support this
      log.warning("Ignoring 'raises' parameter to assertNoErrors")
    self.options.tweak(pythonpath=pythonpath,
                       skip_repeat_calls=skip_repeat_calls)
    errorlog = errors.ErrorLog()
    loader = load_pytd.Loader(self.options.module_name, self.options)
    infer.check_types(
        textwrap.dedent(code), None, loader=loader, errorlog=errorlog,
        options=self.options, cache_unknowns=True)
    if report_errors and len(errorlog):
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))

  def assertNoCrash(self, code, **kwargs):
    self.assertNoErrors(code, report_errors=False, **kwargs)

  def InferAndCheck(self, code, deep=True, pythonpath=(), **kwargs):
    self.options.tweak(pythonpath=pythonpath)
    code = textwrap.dedent(code)
    errorlog = errors.ErrorLog()
    loader = load_pytd.Loader(self.options.module_name, self.options)
    unit, builtins_pytd = infer.infer_types(
        code, errorlog, self.options, loader=loader, deep=deep,
        analyze_annotated=True, cache_unknowns=True, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(unit, builtins_pytd, lossy=False, use_abcs=False,
                             max_union=7, remove_mutable=False)
    return pytd_utils.CanonicalOrdering(unit), errorlog

  def InferFromFile(self, filename, pythonpath):
    self.options.tweak(pythonpath=pythonpath)
    with open(filename, "rb") as fi:
      code = fi.read()
      errorlog = errors.ErrorLog()
      loader = load_pytd.Loader(
          infer.get_module_name(filename, self.options), self.options)
      unit, _ = infer.infer_types(code, errorlog, self.options, loader=loader,
                                  filename=filename, cache_unknowns=True)
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

  def Infer(self, srccode, pythonpath=(), deep=False,
            report_errors=True, analyze_annotated=True, **kwargs):
    types, builtins_pytd = self._InferAndVerify(
        textwrap.dedent(srccode), pythonpath=pythonpath, deep=deep,
        cache_unknowns=True, analyze_annotated=analyze_annotated,
        report_errors=report_errors, **kwargs)
    types = optimize.Optimize(types, builtins_pytd, lossy=False, use_abcs=False,
                              max_union=7, remove_mutable=False)
    types = pytd_utils.CanonicalOrdering(types)
    return types

  def _InferAndVerify(self, src, pythonpath=(), module_name=None,
                      imports_map=None, report_errors=False, quick=False,
                      **kwargs):
    """Infer types for the source code treating it as a module.

    Used by Infer().

    Args:
      src: The source code of a module. Treat it as "__main__".
      pythonpath: --pythonpath as list/tuple of string
      module_name: Name of the module we're analyzing. E.g. "foo.bar.mymodule".
      imports_map: --imports_info data
      report_errors: Whether to fail if the type inferencer reports any errors
        in the program.
      quick: Try to run faster, by avoiding costly computations.
      **kwargs: Keyword parameters to pass through to the type inferencer.

    Raises:
      AssertionError: If report_errors is True and we found errors.
    Returns:
      A pytd.TypeDeclUnit
    """
    self.options.tweak(pythonpath=pythonpath,
                       module_name=module_name,
                       imports_map=imports_map,
                       quick=quick)
    errorlog = errors.ErrorLog()
    loader = load_pytd.Loader(self.options.module_name, self.options)
    unit, builtins_pytd = infer.infer_types(
        src, errorlog, self.options, loader=loader, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    unit = pytd_utils.CanonicalOrdering(unit)
    if report_errors and len(errorlog):
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    return unit, builtins_pytd

  def assertTypesMatchPytd(self, ty, pytd_src, version=None):
    """Parses pytd_src and compares with ty."""
    pytd_tree = parser.parse_string(
        textwrap.dedent(pytd_src), python_version=version)
    pytd_tree = pytd_tree.Visit(visitors.LookupBuiltins(
        builtins.GetBuiltinsAndTyping()[0], full_names=False))
    pytd_tree = pytd_tree.Visit(visitors.LookupLocalTypes())
    pytd_tree = pytd_tree.Visit(
        visitors.ClassTypeToNamedType())
    pytd_tree = pytd_tree.Visit(
        visitors.CanonicalOrderingVisitor(sort_signatures=True))
    pytd_tree.Visit(visitors.VerifyVisitor())
    ty = ty.Visit(visitors.ClassTypeToNamedType())
    ty = ty.Visit(visitors.AdjustSelf(force=True))
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

  def make_code(self, byte_array, name="testcode"):
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, kwonlyargcount=0, nlocals=2, stacksize=2, flags=0,
        consts=[None, 1, 2], names=[], varnames=["x", "y"], filename="",
        name=name, firstlineno=1, lnotab=[], freevars=[], cellvars=[],
        code="".join(chr(c) for c in byte_array),
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
