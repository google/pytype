#!/usr/bin/python2.7
"""Tool for inferring types from Python programs.

'pytype' is a tool for generating pyi from Python programs.

Usage:
  pytype [flags] file.py
"""

from __future__ import print_function

import logging
import os
import sys
import tokenize
import traceback

from pytype import analyze
from pytype import directors
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype.pyc import pyc
from pytype.pyi import parser
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.pytd.parse import builtins as pytd_builtins


log = logging.getLogger(__name__)


def _read_source_file(input_filename):
  try:
    with open(input_filename, "r") as fi:
      return fi.read()
  except IOError:
    raise utils.UsageError("Could not load input file %s" % input_filename)


def check_py(input_filename, errorlog, options, loader):
  """Check the types of one file."""
  src = _read_source_file(input_filename)
  analyze.check_types(
      src=src,
      loader=loader,
      filename=input_filename,
      errorlog=errorlog,
      options=options,
      deep=not options.main_only)


def generate_pyi(input_filename, errorlog, options, loader):
  """Run the inferencer on one file, producing output.

  Args:
    input_filename: name of the file to process
    errorlog: Where error messages go. Instance of errors.ErrorLog.
    options: config.Options object.
    loader: A load_pytd.Loader instance.

  Returns:
    A tuple, (PYI Ast as string, TypeDeclUnit).

  Raises:
    CompileError: If we couldn't parse the input file.
    UsageError: If the input filepath is invalid.
  """
  src = _read_source_file(input_filename)
  mod, builtins = analyze.infer_types(
      src=src,
      errorlog=errorlog,
      options=options,
      loader=loader,
      filename=input_filename,
      deep=not options.main_only,
      maximum_depth=1 if options.quick else 3)
  mod.Visit(visitors.VerifyVisitor())
  mod = optimize.Optimize(mod,
                          builtins,
                          # TODO(kramm): Add FLAGs for these
                          lossy=False,
                          use_abcs=False,
                          max_union=7,
                          remove_mutable=False)
  mod = pytd_utils.CanonicalOrdering(mod, sort_signatures=True)
  result = pytd.Print(mod)
  log.info("=========== pyi optimized =============")
  log.info("\n%s", result)
  log.info("========================================")

  if not result.endswith("\n"):
    result += "\n"
  result_prefix = ""
  if options.quick:
    result_prefix += "# (generated with --quick)\n"
  if result_prefix:
    result = result_prefix + "\n" + result
  return result, mod


def process_one_file(options):
  """Check a .py file or generate a .pyi for it, according to options.

  Args:
    options: config.Options object.

  Returns:
    An error code (0 means no error).
  """
  log.info("Process %s => %s", options.input, options.output)
  errorlog = errors.ErrorLog()
  result = pytd_builtins.DEFAULT_SRC
  ast = pytd_builtins.GetDefaultAst(options.python_version)
  loader = load_pytd.create_loader(options)
  try:
    if options.check:
      check_py(input_filename=options.input,
               errorlog=errorlog,
               options=options,
               loader=loader)
    else:
      result, ast = generate_pyi(input_filename=options.input,
                                 errorlog=errorlog,
                                 options=options,
                                 loader=loader)
  except utils.UsageError as e:
    logging.error("Usage error: %s\n", utils.message(e))
    return 1
  except pyc.CompileError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.error)
  except IndentationError as e:
    errorlog.python_compiler_error(options.input, e.lineno, e.msg)
  except tokenize.TokenError as e:
    msg, (lineno, unused_column) = e.args  # pylint: disable=unbalanced-tuple-unpacking
    errorlog.python_compiler_error(options.input, lineno, msg)
  except directors.SkipFile:
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
  if not options.check:
    if options.output == "-" or not options.output:
      sys.stdout.write(result)
    else:
      log.info("write pyi %r => %r", options.input, options.output)
      with open(options.output, "w") as fi:
        fi.write(result)
      if options.output_pickled:
        write_pickle(ast, loader, options)
  exit_status = handle_errors(errorlog, options)
  # Touch output file upon success.
  if options.touch and not exit_status:
    with open(options.touch, "a"):
      os.utime(options.touch, None)
  return exit_status


def write_pickle(ast, loader, options):
  """Dump a pickle of the ast to a file."""
  try:
    ast = serialize_ast.PrepareForExport(
        options.module_name, options.python_version, ast, loader)
  except parser.ParseError as e:
    if options.nofail:
      ast = serialize_ast.PrepareForExport(
          options.module_name, options.python_version,
          pytd_builtins.GetDefaultAst(options.python_version), loader)
      log.warn("***Caught exception: %s", str(e), exc_info=True)
    else:
      raise
  if options.verify_pickle:
    ast1 = ast.Visit(visitors.LateTypeToClassType())
    ast1 = ast1.Visit(visitors.ClearClassPointers())
    ast2 = loader.load_file(options.module_name, options.output)
    ast2 = ast2.Visit(visitors.ClearClassPointers())
    if not ast1.ASTeq(ast2):
      raise AssertionError()
  serialize_ast.StoreAst(ast, options.output_pickled)


def handle_errors(errorlog, options):
  """Handle the errorlog according to the given options."""
  if options.report_errors:
    if options.output_errors_csv:
      errorlog.print_to_csv_file(options.output_errors_csv)
      return 0  # Command is successful regardless of errors.
    else:
      errorlog.print_to_stderr()
    return 1 if errorlog.has_error() else 0  # exit code
  else:
    return 0


def parse_pyi(options):
  """Tries parsing a PYI file."""
  loader = load_pytd.create_loader(options)
  loader.load_file(options.module_name, options.input)
