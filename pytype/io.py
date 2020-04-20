"""Public interface to top-level pytype functions."""

from __future__ import print_function

import contextlib
import logging
import os
import sys
import tokenize
import traceback

from pytype import __version__
from pytype import analyze
from pytype import config
from pytype import directors
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype.pyc import pyc
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.pytd.parse import builtins as pytd_builtins

import six


log = logging.getLogger(__name__)


# Webpage explaining the pytype error codes
ERROR_DOC_URL = "https://google.github.io/pytype/errors.html"


def read_source_file(input_filename):
  try:
    if six.PY3:
      with open(input_filename, "r", encoding="utf8") as fi:
        return fi.read()
    else:
      with open(input_filename, "rb") as fi:
        return fi.read().decode("utf8")
  except IOError:
    raise utils.UsageError("Could not load input file %s" % input_filename)


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
def _call(analyze_types, input_filename, options, loader):
  """Helper function to call analyze.check/infer_types."""
  src = read_source_file(input_filename)
  errorlog = errors.ErrorLog()
  # 'deep' tells the analyzer whether to analyze functions not called from main.
  deep = not options.main_only
  loader = loader or load_pytd.create_loader(options)
  return errorlog, analyze_types(
      src=src,
      filename=input_filename,
      errorlog=errorlog,
      options=options,
      loader=loader,
      deep=deep)


def check_py(input_filename, options=None, loader=None):
  """Check the types of one file."""
  options = options or config.Options.create(input_filename)
  with config.verbosity_from(options):
    errorlog, _ = _call(analyze.check_types, input_filename, options, loader)
  return errorlog


def generate_pyi(input_filename, options=None, loader=None):
  """Run the inferencer on one file, producing output.

  Args:
    input_filename: name of the file to process
    options: config.Options object.
    loader: A load_pytd.Loader instance.

  Returns:
    A tuple, (errors.ErrorLog, PYI Ast as string, TypeDeclUnit).

  Raises:
    CompileError: If we couldn't parse the input file.
    UsageError: If the input filepath is invalid.
  """
  options = options or config.Options.create(input_filename)
  with config.verbosity_from(options):
    errorlog, (mod, builtins) = _call(
        analyze.infer_types, input_filename, options, loader)
    mod.Visit(visitors.VerifyVisitor())
    mod = optimize.Optimize(mod,
                            builtins,
                            # TODO(kramm): Add FLAGs for these
                            lossy=False,
                            use_abcs=False,
                            max_union=7,
                            remove_mutable=False)
    mod = pytd_utils.CanonicalOrdering(mod, sort_signatures=True)
    result = pytd_utils.Print(mod)
    log.info("=========== pyi optimized =============")
    log.info("\n%s", result)
    log.info("========================================")

  result += "\n"
  if options.quick:
    result = "# (generated with --quick)\n\n" + result
  return errorlog, result, mod


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
  ast = pytd_builtins.GetDefaultAst(options.python_version)
  try:
    if options.check:
      return check_py(
          input_filename=options.input, options=options, loader=loader
      ), None, None
    else:
      errorlog, result, ast = generate_pyi(
          input_filename=options.input, options=options, loader=loader)
  except utils.UsageError as e:
    raise
  except pyc.CompileError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.error)
  except IndentationError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.msg)
  except tokenize.TokenError as e:
    msg, (lineno, unused_column) = e.args  # pylint: disable=unbalanced-tuple-unpacking
    errorlog.python_compiler_error(options.input, lineno, msg)
  except directors.SkipFileError:
    result += "# skip-file found, file not analyzed"
  except Exception as e:  # pylint: disable=broad-except
    if options.nofail:
      log.warn("***Caught exception: %s", str(e), exc_info=True)
      if not options.check:
        result += (  # pytype: disable=name-error
            "# Caught error in pytype: " + str(e).replace("\n", "\n#")
            + "\n# " + "\n# ".join(traceback.format_exc().splitlines()))
    else:
      e.args = (
          str(utils.message(e)) + "\nFile: %s" % options.input,) + e.args[1:]
      raise

  return (errorlog, None, None) if options.check else (errorlog, result, ast)


def _write_pyi_output(options, contents, filename):
  assert filename
  if filename == "-":
    sys.stdout.write(contents)
  else:
    log.info("write pyi %r => %r", options.input, filename)
    with open(filename, "w") as fi:
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
    with open(options.touch, "a"):
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
          options.module_name,
          pytd_builtins.GetDefaultAst(options.python_version), loader)
      log.warn("***Caught exception: %s", str(e), exc_info=True)
    else:
      raise
  if options.verify_pickle:
    ast1 = ast.Visit(visitors.LateTypeToClassType())
    ast1 = ast1.Visit(visitors.ClearClassPointers())
    ast2 = loader.load_file(options.module_name, options.verify_pickle)
    ast2 = ast2.Visit(visitors.ClearClassPointers())
    if not pytd_utils.ASTeq(ast1, ast2):
      raise AssertionError()
  serialize_ast.StoreAst(ast, options.output)


def print_error_doc_url(errorlog):
  names = {e.name for e in errorlog}
  if names:
    doclink = "\nFor more details, see %s" % ERROR_DOC_URL
    if len(names) == 1:
      doclink += "#" + names.pop()
    print(doclink + ".", file=sys.stderr)


@_set_verbosity_from(posarg=1)
def handle_errors(errorlog, options):
  """Handle the errorlog according to the given options."""
  if not options.report_errors:
    return 0

  if options.output_errors_csv:
    errorlog.print_to_csv_file(options.output_errors_csv)
    return 0  # Command is successful regardless of errors.

  errorlog.print_to_stderr()
  print_error_doc_url(errorlog)

  return 1 if errorlog.has_error() else 0  # exit code


@_set_verbosity_from(posarg=0)
def parse_pyi(options):
  """Tries parsing a PYI file."""
  loader = load_pytd.create_loader(options)
  ast = loader.load_file(options.module_name, options.input)
  ast = loader.finish_and_verify_ast(ast)
  if options.output:
    result = "# Internal AST parsed and postprocessed from %s\n\n%s" % (
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
    raise exception_type("Pytype usage error: %s" % utils.message(e))
  except pyc.CompileError as e:
    raise exception_type("Error reading file %s at line %s: %s" %
                         (filename, e.lineno, e.error))
  except tokenize.TokenError as e:
    msg, (lineno, unused_column) = e.args  # pylint: disable=unbalanced-tuple-unpacking
    raise exception_type("Error reading file %s at line %s: %s" %
                         (filename, lineno, msg))
  except directors.SkipFileError:
    raise exception_type("Pytype could not analyze file %s: "
                         "'# skip-file' directive found" % filename)
  except Exception as e:  # pylint: disable=broad-except
    msg = "Pytype error: %s: %s" % (e.__class__.__name__, e.args[0])
    # We need the version check here because six.reraise doesn't work properly
    # in python3
    if sys.version_info[0] == 2:
      _, _, tb = sys.exc_info()
      six.reraise(exception_type, exception_type(msg), tb)
    else:
      raise exception_type(msg).with_traceback(e.__traceback__)
