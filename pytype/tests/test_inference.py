"""Common methods for tests of infer.py."""

import logging
import re
import sys
import textwrap


from pytype import convert_structural
from pytype import errors
from pytype import infer
from pytype.pyc import loadmarshal
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = ("-s" not in sys.argv)


class Infer(object):
  """Calls infer, produces useful output on failure.

  Typically called indirectly from InferenceTest.Infer, which has
  the same args.

  This implements the 'with' protocol. Typical use is (where 'self'
  is the test instance, e.g. test_inference.InferenceTest (below)):

      with self.Infer(src) as ty:
        self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  This code catches exceptions that happen inside Infer(src), so no need to test
  for ty being non-None (although if it is None, the failed method call will be
  caught and reported nicely).

  Comments on the flags:
  The type inferencer has three layers:

  1. Run concrete bytecode
  2. Run abstract bytecode
  3. Convert ("solve") unknowns

  It's useful to be able to test all three things in isolation.

  Solving unknowns in a test where you don't expect unknowns will give you
  more complex debug output and make tests slower. It might also be confusing,
  since the output you're checking is the one from the type converter, causing
  you to suspect the latter as the cause of bugs even though it's not actually
  doing anything.

  As for "deep": this causes all public functions to be called with
  __any_object__ args, so for precise control, you can set deep=False
  and explicitly make the calls.
  """

  # TODO(pludemann): This is possibly a slightly less magical paradigm:
  #   with self.Inferencer(deep=False, solve_unknowns=False) as ty:
  #     ty = i.Infer("""....""")
  #     self.assertOnlyHasReturnType(ty.Lookup(...), ...)

  def __init__(self, test, srccode, deep=False,
               solve_unknowns=False, extract_locals=False,
               reverse_operators=True, extra_verbose=False,
               report_errors=True, pythonpath=(),
               find_pytd_import_ext=".pytd"):
    """Constructor for Infer.

    Args:
      test: the Testcase (see inferenceTest.Infer)
      srccode: the Python source code to do type inferencing on
      deep: see class comments (assume --api - analyize all methods, even those
            that don't have a caller)
      solve_unknowns: try to solve for all ~unknown types
      extract_locals: strip ~unknown types from the output pytd
      reverse_operators: Whether to try e.g. both __add__ and __radd__
      extra_verbose: extra intermeidate output (for debugging)
      report_errors: Whether to fail if the type inferencer reports any erros.
      pythonpath: list of directories for imports
      find_pytd_import_ext: the file extension pattern for imports
    """
    # TODO(pludemann): There are eight possible combinations of these three
    # boolean flags. Do all of these combinations make sense? Or would it be
    # possible to simplify this into something like a "mode" parameter:
    # mode="solve" => deep=True, solve_unknowns=True
    # mode="structural" => deep=True, solve_unknowns=False, extract_locals=False
    # mode="deep" => deep=True, solve_unknowns=False, extract_locals=True
    # mode="main" => deep=False, solve_unknowns=False, extract_locals=True

    self.srccode = textwrap.dedent(srccode)
    self.inferred = None
    self.optimized_types = None
    self.extract_locals = None  # gets set if extract_locals is set (below)
    self.extra_verbose = extra_verbose
    self.canonical_types = None
    # We need to catch any exceptions here and preserve them for __exit__.
    # Exceptions raised in the body of 'with' will be presented to __exit__.
    try:
      self.types = test._InferAndVerify(
          self.srccode, deep=deep, solve_unknowns=solve_unknowns,
          reverse_operators=reverse_operators, cache_unknowns=True,
          report_errors=report_errors,
          pythonpath=pythonpath, find_pytd_import_ext=find_pytd_import_ext)
      self.inferred = self.types
      if extract_locals:
        # Rename "~unknown" to "?"
        self.types = self.types.Visit(visitors.RemoveUnknownClasses())
        # Remove "~list" etc.:
        self.types = convert_structural.extract_local(self.types)
        self.extract_locals = self.types
      # TODO(pludemann): These flags are the same as those in main.py; there
      #                  should be a way of ensuring that they're the same.
      self.types = self.optimized_types = optimize.Optimize(
          self.types, lossy=False, use_abcs=False,
          max_union=7, remove_mutable=False)
      self.types = self.canonical_types = pytd_utils.CanonicalOrdering(
          self.types)
    except Exception:  # pylint: disable=broad-except
      self.types = None
      if not self.__exit__(*sys.exc_info()):
        raise

  def __enter__(self):
    return self.types

  def __exit__(self, error_type, value, traceback):
    if not error_type:
      return
    log.error("*** unittest ERROR *** %s: %s", error_type.__name__, value)
    _PrintErrorDebug("source", self.srccode)
    if self.extra_verbose and self.inferred:
      _PrintErrorDebug("inferred PyTD", pytd.Print(self.inferred))
    if self.extra_verbose and self.optimized_types:
      _PrintErrorDebug("optimized PyTD", pytd.Print(self.optimized_types))
    if self.extra_verbose and self.extract_locals:
      _PrintErrorDebug("extract_locals (removed unknown) PyTD",
                       pytd.Print(self.extract_locals))
    if self.canonical_types:
      _PrintErrorDebug("canonical PyTD", pytd.Print(self.canonical_types))
    return False  # re-raise the exception that was passed in


class InferenceTest(unittest.TestCase):
  """Base class for implementing tests that check PyTD output."""

  PYTHON_VERSION = (2, 7)  # can be overwritten by subclasses

  def setUp(self):
    self.bool = pytd.ClassType("bool")
    self.dict = pytd.ClassType("dict")
    self.float = pytd.ClassType("float")
    self.complex = pytd.ClassType("complex")
    self.int = pytd.ClassType("int")
    if self.PYTHON_VERSION[0] == 2:
      self.long = pytd.ClassType("long")
    self.list = pytd.ClassType("list")
    self.none_type = pytd.ClassType("NoneType")
    self.object = pytd.ClassType("object")
    self.set = pytd.ClassType("set")
    self.frozenset = pytd.ClassType("frozenset")
    self.str = pytd.ClassType("str")
    self.bytes = pytd.ClassType("bytes")
    self.bytearray = pytd.ClassType("bytearray")
    self.tuple = pytd.ClassType("tuple")
    self.unicode = pytd.ClassType("unicode")
    self.generator = pytd.ClassType("generator")
    self.function = pytd.ClassType("function")
    self.anything = pytd.AnythingType()
    self.nothing = pytd.NothingType()
    self.module = pytd.ClassType("module")
    self.file = pytd.ClassType("file")

    # The various union types use pytd_utils.CanonicalOrdering()'s ordering:
    self.intorstr = pytd.UnionType((self.int, self.str))
    self.strorunicodeorbytes = pytd.UnionType(
        (self.str, self.unicode, self.bytes))
    self.intorfloat = pytd.UnionType((self.float, self.int))
    self.intorfloatorstr = pytd.UnionType((self.float, self.int, self.str))
    self.complexorstr = pytd.UnionType((self.complex, self.str))
    # TODO(pludemann): fix the boolorintor... stuff when __builtins__
    #                  is modified to exclude bool from the result
    if self.PYTHON_VERSION[0] == 3:
      self.intorfloatorlong = self.intorfloat
      self.intorfloatorlongorcomplex = pytd.UnionType(
          (self.int, self.float, self.complex))
    else:
      self.intorfloatorlong = pytd.UnionType((self.int, self.float, self.long))
      self.boolorintorfloatorlongorcomplex = pytd.UnionType(
          (self.bool, self.int, self.float, self.long, self.complex))
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

  # For historical reasons (byterun), this method name is snakecase:
  # TODO(kramm): Rename this function.
  # pylint: disable=invalid-name
  def assertNoErrors(self, code, raises=None,
                     pythonpath=(), find_pytd_import_ext=".pytd",
                     report_errors=True):
    """Run an inference smoke test for the given code."""
    if raises is not None:
      # TODO(kramm): support this
      log.warning("Ignoring 'raises' parameter to assertNoErrors")
    errorlog = errors.ErrorLog()
    unit = infer.infer_types(
        textwrap.dedent(code), self.PYTHON_VERSION, errorlog,
        deep=False, solve_unknowns=False, reverse_operators=True,
        pythonpath=pythonpath, find_pytd_import_ext=find_pytd_import_ext,
        cache_unknowns=True)
    if report_errors and errorlog.errors:
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    unit.Visit(visitors.VerifyVisitor())
    return pytd_utils.CanonicalOrdering(unit)

  def assertNoCrash(self, code, **kwargs):
    self.assertNoErrors(code, report_errors=False, **kwargs)

  def InferAndCheck(self, code):
    errorlog = errors.ErrorLog()
    unit = infer.infer_types(
        textwrap.dedent(code), self.PYTHON_VERSION, errorlog, deep=True,
        solve_unknowns=True, reverse_operators=True, cache_unknowns=True)
    unit.Visit(visitors.VerifyVisitor())
    return pytd_utils.CanonicalOrdering(unit), errorlog

  def InferFromFile(self, filename, pythonpath, find_pytd_import_ext=".pytd"):
    errorlog = errors.ErrorLog()
    with open(filename, "rb") as fi:
      unit = infer.infer_types(fi.read(), self.PYTHON_VERSION, errorlog,
                               filename=filename, cache_unknowns=True,
                               pythonpath=pythonpath,
                               find_pytd_import_ext=find_pytd_import_ext)
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
  def HasSignature(cls, func, target):
    for sig in func.signatures:
      if (target.params == tuple(p.type for p in sig.params) and
          cls.SignatureHasReturnType(sig, target.return_type)):
        return True
    return False

  @classmethod
  def HasExactSignature(cls, func, target):
    for sig in func.signatures:
      if (target.params == tuple(p.type for p in sig.params) and
          target.return_type == sig.return_type):
        return True
    return False

  def assertHasOnlySignatures(self, func, *sigs):
    self.assertIsInstance(func, pytd.Function)
    for parameter_types, return_type in sigs:
      target = pytd.Signature(tuple(parameter_types), return_type, (), (),
                              False)
      if not self.HasExactSignature(func, target):
        self.fail("Could not find signature: {name}{target} in {func}".
                  format(name=func.name,
                         target=pytd.Print(target),
                         func=pytd.Print(func)))
    self.assertEqual(len(func.signatures), len(sigs),
                     "{func} has the wrong number of signatures ({has}), "
                     "expected {expect}".
                     format(func=func,
                            has=len(func.signatures), expect=len(sigs)))

  def assertHasSignature(self, func, parameter_types, return_type):
    target = pytd.Signature(tuple(parameter_types), return_type, (), (), False)
    if not self.HasSignature(func, target):
      # TODO(pludemann): don't assume function is 'f'
      self.fail("Could not find signature: f{} in {} ({} in {})".
                format(pytd.Print(target), pytd.Print(func), target, func))

  def assertNotHasSignature(self, func, parameter_types, return_type):
    target = pytd.Signature(tuple(parameter_types), return_type, (), (), False)
    if self.HasSignature(func, target):
      # TODO(pludemann): don't assume function is 'f'
      self.fail("Found signature: f{} -> {} in {}".
                format(pytd.Print(target), pytd.Print(func)))

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

  def Infer(self, srccode, deep=False, solve_unknowns=False,
            reverse_operators=True, extract_locals=False, extra_verbose=False,
            report_errors=True, pythonpath=(), find_pytd_import_ext=".pytd"):
    # Wraps Infer object to make it seem less magical
    # See class Infer for more on the arguments
    return Infer(self, srccode=srccode, deep=deep,
                 solve_unknowns=solve_unknowns, extract_locals=extract_locals,
                 reverse_operators=reverse_operators,
                 extra_verbose=extra_verbose, report_errors=report_errors,
                 pythonpath=pythonpath,
                 find_pytd_import_ext=find_pytd_import_ext)

  def _InferAndVerify(self, src, report_errors=False, **kwargs):
    """Infer types for the source code treating it as a module.

    Used by class Infer (which sets up a 'with' framework)

    Args:
      src: The source code of a module. Treat it as "__main__".
      report_errors: Whether to fail if the type inferencer reports any errors
        in the program.
      **kwargs: Keyword paramters to pass through to the type inferencer.

    Raises:
      AssertionError: If report_errors is True and we found errors.
    Returns:
      A pytd.TypeDeclUnit
    """
    errorlog = errors.ErrorLog()
    unit = infer.infer_types(src, self.PYTHON_VERSION, errorlog, **kwargs)
    unit = pytd_utils.CanonicalOrdering(unit.Visit(visitors.VerifyVisitor()))
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))
    return unit

  def assertTypesMatchPytd(self, ty, pytd_src, version=None):
    """Parses pytd_src and compares with ty."""
    # TODO(pludemann): This is a copy of pytd.parse.parser_test.Parse()
    # TODO(pludemann): Consider using the pytd_tree to call
    #                  assertHasOnlySignatures (or similar) to guard against the
    #                  inferencer adding additional but harmless calls.
    pytd_tree = parser.TypeDeclParser(version=version).Parse(
        textwrap.dedent(pytd_src))
    pytd_tree = pytd_tree.Visit(
        visitors.CanonicalOrderingVisitor(sort_signatures=True))
    pytd_tree.Visit(visitors.VerifyVisitor())
    ty = ty.Visit(visitors.ClassTypeToNamedType())
    ty = ty.Visit(visitors.AdjustSelf(force=True))
    ty = ty.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    ty.Visit(visitors.VerifyVisitor())

    ty_src = pytd.Print(ty) + "\n"
    pytd_tree_src = pytd.Print(pytd_tree) + "\n"

    log.info("====== ty ===")
    _LogLines(log.info, ty_src)
    log.info("=== TypeMatchPytd ===")
    _LogLines(log.info, pytd_tree_src)
    log.info("====== ====== ======")

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
