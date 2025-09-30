"""Common methods for tests of analyze.py."""

import contextlib
import logging
import sys
import textwrap

# from absl import flags
from pytype import analyze
from pytype import config
from pytype import imports_map as imports_map_lib
from pytype import load_pytd
from pytype import module_utils
from pytype.directors import directors
from pytype.imports import pickle_utils
from pytype.platform_utils import path_utils
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.rewrite import analyze as rewrite_analyze
from pytype.tests import test_utils

import unittest

log = logging.getLogger(__name__)


# Make this false if you need to run the debugger inside a test.
CAPTURE_STDOUT = "-s" not in sys.argv


# For ease of importing, re-export some googletest methods. Tweak the names to
# keep the linter happy.
skip = unittest.skip
skip_if = unittest.skipIf
main = unittest.main

_USE_REWRITE = False


def _MatchLoaderConfig(options, loader):
  """Match the |options| with the configuration of |loader|."""
  if not loader:
    return False
  assert isinstance(loader, load_pytd.Loader)
  if options.use_pickled_files != isinstance(
      loader, load_pytd.PickledPyiLoader
  ):
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
  python_version: tuple[int, int] = sys.version_info[:2]

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    # We use class-wide loader to avoid creating a new loader for every test
    # method if not required.
    cls._loader = None

  def setUp(self):
    super().setUp()
    self.options = config.Options.create(
        python_version=self.python_version,
        bind_decorated_methods=True,
        none_is_not_bool=True,
        overriding_renamed_parameter_count_checks=True,
        strict_parameter_checks=True,
        strict_undefined_checks=True,
        strict_primitive_comparisons=True,
        strict_none_binding=True,
        use_fiddle_overlay=True,
        use_functools_partial_overlay=True,
        use_rewrite=_USE_REWRITE,
        validate_version=False,
    )

  @property
  def loader(self):
    if not _MatchLoaderConfig(self.options, self._loader):
      # Create a new loader only if the configuration in the current options
      # does not match the configuration in the current loader.
      self._loader = load_pytd.create_loader(self.options)
    return self._loader

  @property
  def analyze_lib(self):
    return rewrite_analyze if self.options.use_rewrite else analyze

  def ConfigureOptions(self, **kwargs):
    assert (
        "python_version" not in kwargs
    ), "Individual tests cannot set the python_version of the config options."
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
  def Check(
      self,
      code,
      pythonpath=(),
      skip_repeat_calls=True,
      report_errors=True,
      quick=False,
      imports_map=None,
      **kwargs,
  ):
    """Run an inference smoke test for the given code."""
    self.ConfigureOptions(
        skip_repeat_calls=skip_repeat_calls,
        quick=quick,
        **self._GetPythonpathArgs(pythonpath, imports_map),
    )
    try:
      src = _Format(code)
      if test_utils.ErrorMatcher(code).expected:
        self.fail("Cannot assert errors with Check(); use CheckWithErrors()")
      ret = self.analyze_lib.check_types(
          src, loader=self.loader, options=self.options, **kwargs
      )
      errorlog = ret.context.errorlog
    except directors.SkipFileError:
      errorlog = None
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail(f"Checker found {len(errorlog)} errors:\n{errorlog}")

  def assertNoCrash(self, method, code, **kwargs):
    method(code, report_errors=False, **kwargs)

  def _SetUpErrorHandling(
      self, code, pythonpath, analyze_annotated, quick, imports_map
  ):
    code = _Format(code)
    self.ConfigureOptions(
        analyze_annotated=analyze_annotated,
        quick=quick,
        **self._GetPythonpathArgs(pythonpath, imports_map),
    )
    return {"src": code, "options": self.options, "loader": self.loader}

  def InferWithErrors(
      self,
      code,
      pythonpath=(),
      module_name=None,
      analyze_annotated=True,
      quick=False,
      imports_map=None,
      **kwargs,
  ):
    """Runs inference on code expected to have type errors."""
    kwargs.update(
        self._SetUpErrorHandling(
            code, pythonpath, analyze_annotated, quick, imports_map
        )
    )
    self.ConfigureOptions(module_name=module_name)
    ret = self.analyze_lib.infer_types(**kwargs)
    unit = ret.ast
    assert unit is not None
    unit.Visit(visitors.VerifyVisitor())
    unit = optimize.Optimize(
        unit,
        ret.ast_deps,
        lossy=False,
        use_abcs=False,
        max_union=7,
        remove_mutable=False,
    )
    errorlog = ret.context.errorlog
    src = kwargs["src"]
    matcher = test_utils.ErrorMatcher(src)
    matcher.assert_errors_match_expected(errorlog)
    return pytd_utils.CanonicalOrdering(unit), matcher

  def CheckWithErrors(
      self,
      code,
      pythonpath=(),
      analyze_annotated=True,
      quick=False,
      imports_map=None,
      **kwargs,
  ):
    """Check and match errors."""
    kwargs.update(
        self._SetUpErrorHandling(
            code, pythonpath, analyze_annotated, quick, imports_map
        )
    )
    ret = self.analyze_lib.check_types(**kwargs)
    errorlog = ret.context.errorlog
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
            "Cannot assert errors with InferFromFile(); use InferWithErrors()"
        )
      self.ConfigureOptions(
          input=filename,
          module_name=module_utils.get_module_name(filename, pythonpath),
          pythonpath=pythonpath,
      )
      ret = self.analyze_lib.infer_types(
          code, options=self.options, loader=self.loader
      )
      unit = ret.ast
      assert unit is not None
      unit.Visit(visitors.VerifyVisitor())
      return pytd_utils.CanonicalOrdering(unit)

  def assertErrorRegexes(self, matcher, expected_errors):
    matcher.assert_error_regexes(expected_errors)

  def assertErrorSequences(self, matcher, expected_errors):
    matcher.assert_error_sequences(expected_errors)

  def assertDiagnosticRegexes(self, matcher, expected_errors):
    matcher.assert_diagnostic_regexes(expected_errors)

  def assertDiagnosticMessages(self, matcher, expected_errors):
    matcher.assert_diagnostic_messages(expected_errors)

  def _PickleAst(self, ast, module_name):
    assert module_name
    ast = serialize_ast.PrepareForExport(module_name, ast, self.loader)
    return pickle_utils.Serialize(ast)

  def _PickleSource(self, src, module_name):
    ast = serialize_ast.SourceToExportableAst(
        module_name, textwrap.dedent(src), self.loader
    )
    return pickle_utils.Serialize(ast)

  def Infer(
      self,
      srccode,
      pythonpath=(),
      report_errors=True,
      analyze_annotated=True,
      pickle=False,
      module_name=None,
      **kwargs,
  ):
    """Runs inference on srccode."""
    types, deps = self._InferAndVerify(
        _Format(srccode),
        pythonpath=pythonpath,
        analyze_annotated=analyze_annotated,
        module_name=module_name,
        report_errors=report_errors,
        **kwargs,
    )
    types = optimize.Optimize(
        types,
        deps,
        lossy=False,
        use_abcs=False,
        max_union=7,
        remove_mutable=False,
    )
    types = pytd_utils.CanonicalOrdering(types)
    if pickle:
      return self._PickleAst(types, module_name)
    else:
      return types

  def _InferAndVerify(
      self,
      src,
      pythonpath,
      module_name,
      report_errors,
      analyze_annotated,
      imports_map=None,
      quick=False,
      **kwargs,
  ):
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
        module_name=module_name,
        quick=quick,
        use_pickled_files=True,
        analyze_annotated=analyze_annotated,
        **self._GetPythonpathArgs(pythonpath, imports_map),
    )
    if test_utils.ErrorMatcher(src).expected:
      self.fail("Cannot assert errors with Infer(); use InferWithErrors()")
    ret = self.analyze_lib.infer_types(
        src, options=self.options, loader=self.loader, **kwargs
    )
    errorlog = ret.context.errorlog
    unit = ret.ast
    assert unit is not None
    unit.Visit(visitors.VerifyVisitor())
    if report_errors and errorlog:
      errorlog.print_to_stderr()
      self.fail(f"Inferencer found {len(errorlog)} errors:\n{errorlog}")
    return unit, ret.ast_deps

  def assertTypesMatchPytd(self, ty, pytd_src):
    """Parses pytd_src and compares with ty."""
    pytd_tree = parser.parse_string(
        textwrap.dedent(pytd_src),
        options=parser.PyiOptions(python_version=self.python_version),
    )
    pytd_tree = pytd_tree.Visit(
        visitors.LookupBuiltins(self.loader.builtins, full_names=False)
    )
    pytd_tree = pytd_tree.Visit(visitors.LookupLocalTypes())
    pytd_tree = pytd_tree.Visit(visitors.ClassTypeToNamedType())
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
    old_use_pickled_files = self.options.use_pickled_files
    try:
      with test_utils.Tempdir() as d:
        self.ConfigureOptions(
            pythonpath=[""], imports_map=imports_map_lib.ImportsMap()
        )
        use_pickled_files = False
        for dep in deps:
          if len(dep) == 3:
            path, contents, opts = dep
          else:
            path, contents = dep
            opts = {}
          base, ext = path_utils.splitext(path)
          pickle = opts.get("pickle", False)
          use_pickled_files |= pickle
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
          self.options.imports_map.items[base] = filepath
        self.options.use_pickled_files = use_pickled_files
        yield d
    finally:
      self.ConfigureOptions(
          pythonpath=old_pythonpath,
          imports_map=old_imports_map,
          use_pickled_files=old_use_pickled_files,
      )


def _PrintErrorDebug(descr, value):
  log.error("=============== %s ===========", descr)
  _LogLines(log.error, value)
  log.error("=========== end %s ===========", descr)


def _LogLines(log_cmd, lines):
  for l in lines.split("\n"):
    log_cmd("%s", l)
