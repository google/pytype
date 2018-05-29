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
    # The test class (type of |self|) constructor is required to initialize the
    # 'python_version' attribute.
    assert hasattr(self, "python_version")
    if self.python_version:
      self.options = config.Options.create(
          python_version=self.python_version,
          python_exe=utils.get_python_exe(self.python_version))
    else:
      # If the target Python version is None, it means that the test runner
      # will set it before running the test. Hence, we create an empty Options
      # object which can be configured by the test runner.
      self.options = config.Options.create()

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
    if self.options.python_version is None:
      self.options.python_version = self.python_version
    self.options.tweak(
        python_exe=utils.get_python_exe(self.options.python_version))

  # For historical reasons (byterun), this method name is snakecase:
  # TODO(kramm): Rename this function.
  # pylint: disable=invalid-name
  def Check(self, code, pythonpath=(), skip_repeat_calls=True,
            report_errors=True, filename=None, **kwargs):
    """Run an inference smoke test for the given code."""
    self.ConfigureOptions(skip_repeat_calls=skip_repeat_calls,
                          pythonpath=pythonpath)
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

  def _SetUpErrorHandling(self, code, pythonpath, analyze_annotated, quick):
    code = textwrap.dedent(code)
    errorlog = errors.ErrorLog()
    self.ConfigureOptions(
        pythonpath=pythonpath, analyze_annotated=analyze_annotated, quick=quick)
    return {"src": code, "errorlog": errorlog, "options": self.options,
            "loader": self.loader}

  def InferWithErrors(self, code, deep=True, pythonpath=(),
                      analyze_annotated=True, quick=False, **kwargs):
    kwargs.update(
        self._SetUpErrorHandling(code, pythonpath, analyze_annotated, quick))
    unit, builtins_pytd = analyze.infer_types(deep=deep, **kwargs)
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(unit, builtins_pytd, lossy=False, use_abcs=False,
                             max_union=7, remove_mutable=False)
    return pytd_utils.CanonicalOrdering(unit), kwargs["errorlog"]

  def CheckWithErrors(self, code, deep=True, pythonpath=(),
                      analyze_annotated=True, quick=False, **kwargs):
    kwargs.update(
        self._SetUpErrorHandling(code, pythonpath, analyze_annotated, quick))
    analyze.check_types(filename="<inline>", deep=deep, **kwargs)
    return kwargs["errorlog"]

  def InferFromFile(self, filename, pythonpath):
    with open(filename, "r") as fi:
      code = fi.read()
      errorlog = errors.ErrorLog()
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
        module_name, self.python_version, ast, self.loader)
    return serialize_ast.StoreAst(ast)

  def Infer(self, srccode, pythonpath=(), deep=True,
            report_errors=True, analyze_annotated=True, pickle=False,
            module_name=None, **kwargs):
    types, builtins_pytd = self._InferAndVerify(
        textwrap.dedent(srccode), pythonpath=pythonpath, deep=deep,
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
    errorlog = errors.ErrorLog()
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


class TargetIndependentTest(BaseTest):
  """Class for tests which are independent of the target Python version.

  Test methods in subclasses will operate on Python code which does not use any
  feature specific to a Python version, including type annotations.
  """

  # TODO(sivachandra): Move this constructor to BaseTest once test bucketization
  # is complete.
  def __init__(self, *args, **kwargs):
    super(TargetIndependentTest, self).__init__(*args, **kwargs)
    self.python_version = None


class TargetPython27FeatureTest(BaseTest):
  """Class for tests which depend on a Python 2.7 feature.

  Test methods in subclasses will test Pytype on a Python 2.7 feature.
  """

  def __init__(self, *args, **kwargs):
    super(TargetPython27FeatureTest, self).__init__(*args, **kwargs)
    self.python_version = (2, 7)


class TargetPython3BasicTest(BaseTest):
  """Class for tests using type annotations as the only Python 3 feature.

  Test methods in subclasses will test Pytype on Python code stubs which use
  type annotations as the only Python 3 feature.
  """

  def __init__(self, *args, **kwargs):
    super(TargetPython3BasicTest, self).__init__(*args, **kwargs)
    self.python_version = (3, 6)


class TargetPython3FeatureTest(TargetPython3BasicTest):
  """Class for tests which depend on a Python 3 feature beyond type annotations.

  Test methods in subclasses will test Pytype on a Python 3.6 feature.
  """
  pass


class OperatorsTestMixin(object):
  """Mixin providing uitlities for operators tests."""

  def check_expr(self, expr, assignments, expected_return):  # pylint: disable=invalid-name
    # Note that testing "1+2" as opposed to "x=1; y=2; x+y" doesn't really test
    # anything because the peephole optimizer converts "1+2" to "3" and __add__
    # isn't called. So, need to defeat the optimizer by replacing the constants
    # by variables, which will result in calling __add__ et al.

    # Join the assignments with ";" to avoid figuring out the exact indentation:
    assignments = "; ".join(assignments)
    src = """
      def f():
        {assignments}
        return {expr}
      f()
    """.format(expr=expr, assignments=assignments)
    ty = self.Infer(src, deep=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), expected_return)

  def check_binary(self, function_name, op):  # pylint: disable=invalid-name
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self, unused_x):
          return 3j
      class Bar(object):
        pass
      def f():
        return Foo() {op} Bar()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def check_unary(self, function_name, op, ret=None):  # pylint: disable=invalid-name
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), ret or self.complex)

  def check_reverse(self, function_name, op):  # pylint: disable=invalid-name
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      class Bar(Foo):
        def __r{function_name}__(self, x):
          return "foo"
      def f():
        return Foo() {op} 1  # use Foo.__{function_name}__
      def g():
        return 1 {op} Bar()  # use Bar.__r{function_name}__
      def h():
        return Foo() {op} Bar()  # use Bar.__r{function_name}__
      def i():
        return Foo() {op} Foo()  # use Foo.__{function_name}__
      f(); g(); h(); i()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)
    self.assertHasReturnType(ty.Lookup("g"), self.str)
    self.assertHasReturnType(ty.Lookup("h"), self.str)
    self.assertHasReturnType(ty.Lookup("i"), self.complex)

  def check_inplace(self, function_name, op):  # pylint: disable=invalid-name
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      def f():
        x = Foo()
        x {op} None
        return x
      f()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)


# TODO(sivachandra): Remove this class infavor of the class OperatorsTestMixin.
# It is not a drop-in-replacement currently, but there is no reason why it
# cannot be made one.
class InplaceTestMixin(object):
  """Mixin providing a method to check in-place operators."""

  def _check_inplace(self, op, assignments, expected_return):  # pylint: disable=invalid-name
    assignments = "; ".join(assignments)
    src = """
      def f(x, y):
        {assignments}
        x {op}= y
        return x
      a = f(1, 2)
    """.format(assignments=assignments, op=op)
    ty = self.Infer(src, deep=False)
    self.assertTypeEquals(ty.Lookup("a").type, expected_return)


class TestCollectionsMixin(object):
  """Mixin providing utils for tests on the collections module."""

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error):  # pylint: disable=invalid-name
    result = self.CheckWithErrors("""\
            import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # line 5
    """.format(obj=obj, good_arg=good_arg, bad_arg=bad_arg))
    self.assertErrorLogIs(result, [(5, "wrong-arg-types", error)])


class MakeCodeMixin(object):
  """Mixin providing a method to make a code object from bytecode."""

  def make_code(self, int_array, name="testcode"):  # pylint: disable=invalid-name
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, kwonlyargcount=0, nlocals=2, stacksize=2, flags=0,
        consts=[None, 1, 2], names=[], varnames=["x", "y"], filename="",
        name=name, firstlineno=1, lnotab=[], freevars=[], cellvars=[],
        code=compat.int_array_to_bytes(int_array),
        python_version=self.python_version)


def _PrintErrorDebug(descr, value):
  log.error("=============== %s ===========", descr)
  _LogLines(log.error, value)
  log.error("=========== end %s ===========", descr)


def _LogLines(log_cmd, lines):
  for l in lines.split("\n"):
    log_cmd("%s", l)


def _ReplacementMethod(python_version, actual_method):
  def Replacement(self, *args, **kwargs):
    self.python_version = python_version
    # The "options" attribute should have been set by the setUp method of
    # the test class.
    assert hasattr(self, "options")
    self.options.tweak(
        python_version=self.python_version,
        python_exe=utils.get_python_exe(self.python_version))
    return actual_method(self, *args, **kwargs)
  return Replacement


def _ReplaceMethods(toplevel):
  if not isinstance(toplevel, type):
    return False
  if issubclass(toplevel, TargetIndependentTest):
    return True
  return False


def main(toplevels, is_main_module=True, debugging=False):
  """The main method for tests subclassing one of the above classes.

  This function should be called unconditionally, and typically as follows:

    main(globals(), __name__ == "__main__")

  This enables one to run the tests using the 'python -m unittest ...' command,
  which does run the main test module as the main interpreter module.
  Call to unittest.main is made only if |is_main_module| is true.

  Arguments:
    toplevels: The toplevels defined in the main test module.
    is_main_module: True if the main test module is the main module in the
                    interpreter.
    debugging: Enable debug logs.
  """
  # TODO(ampere): This is just a useful hack. Should be replaced with real
  #               argument handling.
  level = logging.DEBUG if debugging or len(sys.argv) > 1 else logging.WARNING
  debug.set_logging_level(level)
  # We want to run tests in a few buckets twice: once with target Python
  # version set to 2.7, and another time with target Python version set to 3.6.
  # So, for tests falling in such buckets, we replace the single test method
  # with two methods, one each for the target version 2.7 and 3.6 respectively.
  for _, tp in toplevels.items():
    if _ReplaceMethods(tp):
      for attr_name in dir(tp):
        attr = getattr(tp, attr_name)
        if attr_name.startswith("test") and callable(attr):
          setattr(tp, "%s_py2" % attr_name,
                  _ReplacementMethod((2, 7), attr))
          setattr(tp, "%s_py3" % attr_name,
                  _ReplacementMethod((3, 6), attr))
          delattr(tp, attr_name)
  if is_main_module:
    unittest.main()
