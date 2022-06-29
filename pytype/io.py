"""Public interface to top-level pytype functions."""

import contextlib
import logging
import os
import sys
import traceback

import libcst

from pytype import __version__
from pytype import analyze
from pytype import config
from pytype import constant_folding
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype.directors import directors
from pytype.pyc import pyc
from pytype.pyi import parser
from pytype.pytd import builtin_stubs as pytd_builtins
from pytype.pytd import optimize
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors


log = logging.getLogger(__name__)


# Webpage explaining the pytype error codes
ERROR_DOC_URL = "https://google.github.io/pytype/errors.html"


def read_source_file(input_filename, open_function=open):
  try:
    with open_function(input_filename, "r", encoding="utf8") as fi:
      return fi.read()
  except OSError as e:
    raise utils.UsageError(f"Could not load input file {input_filename}") from e


def _set_verbosity_from(posarg):
  """Decorator to set the verbosity for a function that takes an options arg.

  Assumes that the function has an argument named `options` that is a
  config.Options object.

  Arguments:
    posarg: The index of `options` in the positional arguments.

  Returns:
    The decorator.
  """
  def decorator(f):
    def wrapper(*args, **kwargs):
      options = kwargs.get("options", args[posarg])
      with config.verbosity_from(options):
        return f(*args, **kwargs)
    return wrapper
  return decorator


@_set_verbosity_from(posarg=2)
def _call(analyze_types, src, options, loader):
  """Helper function to call analyze.check/infer_types."""
  # 'deep' tells the analyzer whether to analyze functions not called from main.
  deep = not options.main_only
  loader = loader or load_pytd.create_loader(options)
  return analyze_types(
      src=src,
      filename=options.input,
      options=options,
      loader=loader,
      deep=deep)


def check_py(src, options=None, loader=None):
  """Check the types of a string of source code."""
  options = options or config.Options.create()
  with config.verbosity_from(options):
    ret = _call(analyze.check_types, src, options, loader)
  return ret.errorlog


def generate_pyi(src, options=None, loader=None):
  """Run the inferencer on a string of source code, producing output.

  Args:
    src: The source code.
    options: config.Options object.
    loader: A load_pytd.Loader instance.

  Returns:
    A tuple, (errors.ErrorLog, PYI Ast as string, TypeDeclUnit).

  Raises:
    CompileError: If we couldn't parse the input file.
    UsageError: If the input filepath is invalid.
  """
  options = options or config.Options.create()
  with config.verbosity_from(options):
    ret = _call(analyze.infer_types, src, options, loader)
    mod = ret.ast
    mod.Visit(visitors.VerifyVisitor())
    mod = optimize.Optimize(mod,
                            ret.builtins,
                            lossy=False,
                            use_abcs=False,
                            max_union=7,
                            remove_mutable=False)
    mod = pytd_utils.CanonicalOrdering(mod)
    result = pytd_utils.Print(mod)
    log.info("=========== pyi optimized =============")
    log.info("\n%s", result)
    log.info("========================================")

  result += "\n"
  if options.quick:
    result = "# (generated with --quick)\n\n" + result
  return ret.errorlog, result, mod


@_set_verbosity_from(posarg=0)
def check_or_generate_pyi(options, loader=None):
  """Returns generated errors and result pyi or None if it's only check.

  Args:
    options: config.Options object.
    loader: load_pytd.Loader object.

  Returns:
    A tuple, (errors.ErrorLog, PYI Ast as string or None, AST or None).
  """

  errorlog = errors.ErrorLog()
  result = pytd_builtins.DEFAULT_SRC
  ast = pytd_builtins.GetDefaultAst(
      parser.PyiOptions.from_toplevel_options(options))
  try:
    src = read_source_file(options.input, options.open_function)
    if options.check:
      return check_py(src=src, options=options, loader=loader), None, None
    else:
      errorlog, result, ast = generate_pyi(
          src=src, options=options, loader=loader)
  except utils.UsageError:
    raise
  except pyc.CompileError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.error)
  except constant_folding.ConstantError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.message)
  except IndentationError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.msg)
  except libcst.ParserSyntaxError as e:
    # TODO(rechen): We can get rid of this branch once we delete
    # directors.parser_libcst.
    errorlog.python_compiler_error(options.input, e.raw_line, e.message)
  except SyntaxError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.msg)
  except directors.SkipFileError:
    result += "# skip-file found, file not analyzed"
  except Exception as e:  # pylint: disable=broad-except
    if options.nofail:
      log.warning("***Caught exception: %s", str(e), exc_info=True)
      if not options.check:
        result += (
            "# Caught error in pytype: " + str(e).replace("\n", "\n#")
            + "\n# " + "\n# ".join(traceback.format_exc().splitlines()))
    else:
      e.args = (
          str(utils.message(e)) + f"\nFile: {options.input}",) + e.args[1:]
      raise

  return (errorlog, None, None) if options.check else (errorlog, result, ast)


def _write_pyi_output(options, contents, filename):
  assert filename
  if filename == "-":
    sys.stdout.write(contents)
  else:
    log.info("write pyi %r => %r", options.input, filename)
    with options.open_function(filename, "w") as fi:
      fi.write(contents)


@_set_verbosity_from(posarg=0)
def process_one_file(options):
  """Check a .py file or generate a .pyi for it, according to options.

  Args:
    options: config.Options object.

  Returns:
    An error code (0 means no error).
  """

  log.info("Process %s => %s", options.input, options.output)
  loader = load_pytd.create_loader(options)
  try:
    errorlog, result, ast = check_or_generate_pyi(options, loader)
  except utils.UsageError as e:
    logging.error("Usage error: %s\n", utils.message(e))
    return 1

  if not options.check:
    if options.pickle_output:
      pyi_output = options.verify_pickle
    else:
      pyi_output = options.output
    # Write out the pyi file.
    if pyi_output:
      _write_pyi_output(options, result, pyi_output)
    # Write out the pickle file.
    if options.pickle_output:
      log.info("write pickle %r => %r", options.input, options.output)
      write_pickle(ast, options, loader)
  exit_status = handle_errors(errorlog, options)

  # If we have set return_success, set exit_status to 0 after the regular error
  # handler has been called.
  if options.return_success:
    exit_status = 0

  # Touch output file upon success.
  if options.touch and not exit_status:
    with options.open_function(options.touch, "a"):
      os.utime(options.touch, None)
  return exit_status


@_set_verbosity_from(posarg=1)
def write_pickle(ast, options, loader=None):
  """Dump a pickle of the ast to a file."""
  loader = loader or load_pytd.create_loader(options)
  try:
    ast = serialize_ast.PrepareForExport(options.module_name, ast, loader)
  except parser.ParseError as e:
    if options.nofail:
      ast = serialize_ast.PrepareForExport(
          options.module_name, loader.get_default_ast(), loader)
      log.warning("***Caught exception: %s", str(e), exc_info=True)
    else:
      raise
  if options.verify_pickle:
    ast1 = ast.Visit(visitors.LateTypeToClassType())
    ast1 = ast1.Visit(visitors.ClearClassPointers())
    ast2 = loader.load_file(options.module_name, options.verify_pickle)
    ast2 = ast2.Visit(visitors.ClearClassPointers())
    if not pytd_utils.ASTeq(ast1, ast2):
      raise AssertionError()
  serialize_ast.StoreAst(ast, options.output, options.open_function,
                         is_package=options.module_name.endswith(".__init__"),
                         metadata=options.pickle_metadata)


def print_error_doc_url(errorlog):
  names = {e.name for e in errorlog}
  if names:
    doclink = f"\nFor more details, see {ERROR_DOC_URL}"
    if len(names) == 1:
      doclink += "#" + names.pop()
    print(doclink, file=sys.stderr)


@_set_verbosity_from(posarg=1)
def handle_errors(errorlog, options):
  """Handle the errorlog according to the given options."""
  if not options.report_errors:
    return 0

  if options.output_errors_csv:
    errorlog.print_to_csv_file(options.output_errors_csv, options.open_function)
    return 0  # Command is successful regardless of errors.

  errorlog.print_to_stderr(color=options.color)
  print_error_doc_url(errorlog)

  return 1 if errorlog.has_error() else 0  # exit code


@_set_verbosity_from(posarg=0)
def parse_pyi(options):
  """Tries parsing a PYI file."""
  loader = load_pytd.create_loader(options)
  ast = loader.load_file(options.module_name, options.input)
  ast = loader.finish_and_verify_ast(ast)
  if options.output:
    result = "# Internal AST parsed and postprocessed from {}\n\n{}".format(
        options.input, pytd_utils.Print(ast))
    _write_pyi_output(options, result, options.output)
  return ast


def get_pytype_version():
  return __version__.__version__


@contextlib.contextmanager
def wrap_pytype_exceptions(exception_type, filename=""):
  """Catch pytype errors and reraise them as a single exception type.

  NOTE: This will also wrap non-pytype errors thrown within the body of the
  code block; it is therefore recommended to use this to wrap a single function
  call.

  Args:
    exception_type: The class to wrap exceptions in.
    filename: A filename to use in error messages.

  Yields:
    nothing, just calls the code block.
  """
  try:
    yield
  except utils.UsageError as e:
    raise exception_type(f"Pytype usage error: {utils.message(e)}") from e
  except pyc.CompileError as e:
    raise exception_type("Error reading file %s at line %s: %s" %
                         (filename, e.lineno, e.error)) from e
  except libcst.ParserSyntaxError as e:
    # TODO(rechen): We can get rid of this branch once we delete
    # directors.parser_libcst.
    raise exception_type("Error reading file %s at line %s: %s" %
                         (filename, e.raw_line, e.message)) from e
  except SyntaxError as e:
    raise exception_type("Error reading file %s at line %s: %s" %
                         (filename, e.lineno, e.msg)) from e
  except directors.SkipFileError as e:
    raise exception_type("Pytype could not analyze file %s: "
                         "'# skip-file' directive found" % filename) from e
  except pytd_utils.LoadPickleError as e:
    raise exception_type(f"Error analyzing file {filename}: Could not load "
                         f"serialized dependency {e.filename}") from e
  except Exception as e:  # pylint: disable=broad-except
    msg = f"Pytype error: {e.__class__.__name__}: {e.args[0]}"
    raise exception_type(msg).with_traceback(e.__traceback__)
