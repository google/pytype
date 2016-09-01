"""Common methods for tests of infer.py."""

import logging
import re
import sys
import textwrap


from pytype import config
from pytype import directors
from pytype import errors
from pytype import infer
from pytype.pyc import loadmarshal
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


class InferenceTest(unittest.TestCase):
  """Base class for implementing tests that check PyTD output."""

  PYTHON_VERSION = (2, 7)  # can be overwritten by subclasses
  PYTHON_EXE = None  # can be overwritten by subclasses

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
    if self.PYTHON_VERSION[0] == 2:
      self.long = t("long")
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
    self.function = t("function")
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
    if self.PYTHON_VERSION[0] == 3:
      self.intorfloatorlong = self.intorfloat
      self.intorfloatorlongorcomplex = pytd.UnionType(
          (self.int, self.float, self.complex))
    else:
      self.intorfloatorlong = pytd.UnionType((self.int, self.float, self.long))
      self.intorfloatorlongorcomplex = pytd.UnionType(
          (self.int, self.float, self.long, self.complex))
    self.int_tuple = pytd.HomogeneousContainerType(self.tuple, (self.int,))
    self.nothing_tuple = pytd.HomogeneousContainerType(self.tuple,
                                                       (self.nothing,))
    self.intorfloat_tuple = pytd.HomogeneousContainerType(self.tuple,
                                                          (self.intorfloat,))
    self.int_set = pytd.HomogeneousContainerType(self.set, (self.int,))
    self.intorfloat_set = pytd.HomogeneousContainerType(self.set,
                                                        (self.intorfloat,))
    # TODO(pludemann): simplify this (test_and2)
    self.unknown_frozenset = pytd.HomogeneousContainerType(
        self.frozenset, (self.anything,))
    self.float_frozenset = pytd.HomogeneousContainerType(self.frozenset,
                                                         (self.float,))
    self.empty_frozenset = pytd.HomogeneousContainerType(self.frozenset,
                                                         (self.nothing,))
    self.int_list = pytd.HomogeneousContainerType(self.list, (self.int,))
    self.str_list = pytd.HomogeneousContainerType(self.list, (self.str,))
    self.intorfloat_list = pytd.HomogeneousContainerType(self.list,
                                                         (self.intorfloat,))
    self.intorstr_list = pytd.HomogeneousContainerType(self.list,
                                                       (self.intorstr,))
    self.anything_list = pytd.HomogeneousContainerType(self.list,
                                                       (self.anything,))
    self.nothing_list = pytd.HomogeneousContainerType(self.list,
                                                      (self.nothing,))
    self.int_int_dict = pytd.GenericType(self.dict, (self.int, self.int))
    self.int_str_dict = pytd.GenericType(self.dict, (self.int, self.str))
    self.str_int_dict = pytd.GenericType(self.dict, (self.str, self.int))
    self.nothing_nothing_dict = pytd.GenericType(self.dict,
                                                 (self.nothing, self.nothing))

  def _InitErrorLog(self, src, filename=None):
    errorlog = errors.ErrorLog()
    director = directors.Director(src, errorlog, filename, ())
    errorlog.set_error_filter(director.should_report_error)
    return errorlog

  # For historical reasons (byterun), this method name is snakecase:
  # TODO(kramm): Rename this function.
  # pylint: disable=invalid-name
  def assertNoErrors(self, code, raises=None,
                     pythonpath=(),
                     report_errors=True):
    """Run an inference smoke test for the given code."""
    if raises is not None:
      # TODO(kramm): support this
      log.warning("Ignoring 'raises' parameter to assertNoErrors")
    self.options.tweak(pythonpath=pythonpath)
    errorlog = self._InitErrorLog(code)
    unit = infer.infer_types(
        textwrap.dedent(code), errorlog, self.options,
        deep=True, solve_unknowns=True, cache_unknowns=True)
    if report_errors and errorlog.has_error():
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    unit.Visit(visitors.VerifyVisitor())
    return pytd_utils.CanonicalOrdering(unit)

  def assertNoCrash(self, code, **kwargs):
    self.assertNoErrors(code, report_errors=False, **kwargs)

  def InferAndCheck(self, code, deep=True, pythonpath=(), **kwargs):
    self.options.tweak(pythonpath=pythonpath)
    code = textwrap.dedent(code)
    errorlog = self._InitErrorLog(code)
    unit = infer.infer_types(
        code, errorlog, self.options, deep=deep, cache_unknowns=True, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    return pytd_utils.CanonicalOrdering(unit), errorlog

  def InferFromFile(self, filename, pythonpath):
    self.options.tweak(pythonpath=pythonpath)
    with open(filename, "rb") as fi:
      code = fi.read()
      errorlog = self._InitErrorLog(code, filename)
      unit = infer.infer_types(code, errorlog, self.options,
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
      # TODO(pludemann): don't assume function is 'f'
      self.fail("Could not find signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type), pytd.Print(func)))

  def assertNotHasSignature(self, func, parameter_types, return_type):
    if self.HasSignature(func, parameter_types, return_type):
      # TODO(pludemann): don't assume function is 'f'
      self.fail("Found signature: f{} in {}".format(
          self.PrintSignature(parameter_types, return_type), pytd.Print(func)))

  def assertTypeEquals(self, t1, t2):
    self.assertEquals(t1, t2,
                      "Type %r != %r" % (pytd.Print(t1),
                                         pytd.Print(t2)))

  def assertOnlyHasReturnType(self, func, t):
    """Test that a given return type is the only one."""
    ret = pytd_utils.JoinTypes(sig.return_type
                               for sig in func.signatures)
    self.assertEquals(t, ret,
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
      self.assertEquals(t, ret,
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
      self.assertEquals(len(sig.params), 1)
      param1, = sig.params
      self.assertEquals(param1.type, sig.return_type,
                        "Not identity: %r" % pytd.Print(func))

  def assertErrorLogContains(self, errorlog, regexp):
    for error in errorlog:
      if re.compile(regexp, re.I | re.S).search(str(error)):
        return
    print >>sys.stderr, "Couldn't find regexp %r in errors:" % regexp
    errorlog.print_to_stderr()
    raise AssertionError("Couldn't find regexp %r in errors" % regexp)

  def assertErrorLogDoesNotContain(self, errorlog, regexp):
    for error in errorlog:
      if re.compile(regexp, re.I | re.S).search(str(error)):
        print >>sys.stderr, "Found regexp %r in errors:" % regexp
        errorlog.print_to_stderr()
        raise AssertionError("Found regexp %r in errors" % regexp)

  def assertErrorLogIs(self, errorlog, expected_lines_and_errors):
    actual_errors = {(error.lineno, error.name): error
                     for error in errorlog}
    for pattern in expected_lines_and_errors:
      line = pattern[0]
      name = pattern[1]
      regexp = pattern[2] if len(pattern) > 2 else None
      error = actual_errors.get((line, name))
      if error is None:
        errorlog.print_to_stderr()
        raise AssertionError("Error %s not found on line %d %r" % (
            name, line, " " + repr(regexp) if regexp else ""))
      if regexp and not re.search(regexp, error.message, flags=re.S):
        errorlog.print_to_stderr()
        raise AssertionError("Bad error message: %r doesn't match %r" % (
            error.message, regexp))
      del actual_errors[(line, name)]
    if actual_errors:
      any_error = next(actual_errors.items())
      errorlog.print_to_stderr()
      raise AssertionError("Unexpected error:\n%s" % any_error)

  def Infer(self, srccode, pythonpath=(), deep=False, solve_unknowns=False,
            extract_locals=False, report_errors=True, **kwargs):
    types = self._InferAndVerify(
        textwrap.dedent(srccode), pythonpath=pythonpath, deep=deep,
        cache_unknowns=True, solve_unknowns=solve_unknowns,
        extract_locals=extract_locals, report_errors=report_errors, **kwargs)
    types = optimize.Optimize(types, lossy=False, use_abcs=False,
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
      **kwargs: Keyword paramters to pass through to the type inferencer.

    Raises:
      AssertionError: If report_errors is True and we found errors.
    Returns:
      A pytd.TypeDeclUnit
    """
    self.options.tweak(pythonpath=pythonpath,
                       module_name=module_name,
                       imports_map=imports_map,
                       quick=quick)
    errorlog = self._InitErrorLog(src)
    unit = infer.infer_types(src, errorlog, self.options, **kwargs)
    unit = pytd_utils.CanonicalOrdering(unit.Visit(visitors.VerifyVisitor()))
    if report_errors and errorlog.has_error():
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    return unit

  def assertTypesMatchPytd(self, ty, pytd_src, version=None):
    """Parses pytd_src and compares with ty."""
    # TODO(pludemann): This is a copy of pytd.parse.parser_test_base.Parse()
    # TODO(pludemann): Consider using the pytd_tree to call
    #                  assertHasOnlySignatures (or similar) to guard against the
    #                  inferencer adding additional but harmless calls.
    pytd_tree = parser.TypeDeclParser().Parse(
        textwrap.dedent(pytd_src), version=version)
    pytd_tree = pytd_tree.Visit(
        visitors.LookupBuiltins(builtins.GetBuiltinsAndTyping()[0]))
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
  if debugging or len(sys.argv) > 1:
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.WARNING)
  unittest.main()

if __name__ == "__main__":
  main()
