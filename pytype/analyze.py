"""Code for checking and inferring types."""

import logging
import subprocess

from pytype import context
from pytype import convert_structural
from pytype import debug
from pytype import metrics
from pytype.abstract import abstract_utils
from pytype.pytd import pytd_utils
from pytype.pytd import visitors

log = logging.getLogger(__name__)

# How deep to follow call chains:
INIT_MAXIMUM_DEPTH = 4  # during module loading
MAXIMUM_DEPTH = 3  # during non-quick analysis
QUICK_CHECK_MAXIMUM_DEPTH = 2  # during quick checking
QUICK_INFER_MAXIMUM_DEPTH = 1  # during quick inference


def check_types(src, filename, errorlog, options, loader,
                deep=True, init_maximum_depth=INIT_MAXIMUM_DEPTH,
                maximum_depth=None, **kwargs):
  """Verify the Python code."""
  ctx = context.Context(
      errorlog=errorlog,
      options=options,
      generate_unknowns=False,
      loader=loader,
      **kwargs)
  loc, defs = ctx.vm.run_program(src, filename, init_maximum_depth)
  snapshotter = metrics.get_metric("memory", metrics.Snapshot)
  snapshotter.take_snapshot("analyze:check_types:tracer")
  if deep:
    if maximum_depth is None:
      maximum_depth = (
          QUICK_CHECK_MAXIMUM_DEPTH if options.quick else MAXIMUM_DEPTH)
    ctx.vm.analyze(loc, defs, maximum_depth=maximum_depth)
  snapshotter.take_snapshot("analyze:check_types:post")
  _maybe_output_debug(options, ctx.program)


def infer_types(src,
                errorlog,
                options,
                loader,
                filename=None,
                deep=True,
                init_maximum_depth=INIT_MAXIMUM_DEPTH,
                show_library_calls=False,
                maximum_depth=None,
                ctx=None,
                **kwargs):
  """Given Python source return its types.

  Args:
    src: A string containing Python source code.
    errorlog: Where error messages go. Instance of errors.ErrorLog.
    options: config.Options object
    loader: A load_pytd.Loader instance to load PYI information.
    filename: Filename of the program we're parsing.
    deep: If True, analyze all functions, even the ones not called by the main
      execution flow.
    init_maximum_depth: Depth of analysis during module loading.
    show_library_calls: If True, call traces are kept in the output.
    maximum_depth: Depth of the analysis. Default: unlimited.
    ctx: An instance of context.Context, in case the caller wants to
      instantiate and retain the abstract context used for type inference.
    **kwargs: Additional parameters to pass to context.Context
  Returns:
    A tuple of (ast: TypeDeclUnit, builtins: TypeDeclUnit)
  Raises:
    AssertionError: In case of a bad parameter combination.
  """
  if not ctx:
    ctx = context.Context(
        errorlog=errorlog,
        options=options,
        generate_unknowns=options.protocols,
        store_all_calls=not deep,
        loader=loader,
        **kwargs)
  loc, defs = ctx.vm.run_program(src, filename, init_maximum_depth)
  log.info("===Done running definitions and module-level code===")
  snapshotter = metrics.get_metric("memory", metrics.Snapshot)
  snapshotter.take_snapshot("analyze:infer_types:tracer")
  if deep:
    if maximum_depth is None:
      if not options.quick:
        maximum_depth = MAXIMUM_DEPTH
      elif options.analyze_annotated:
        # Since there's no point in analyzing annotated functions for inference,
        # the presence of this option means that the user wants checking, too.
        maximum_depth = QUICK_CHECK_MAXIMUM_DEPTH
      else:
        maximum_depth = QUICK_INFER_MAXIMUM_DEPTH
    ctx.exitpoint = ctx.vm.analyze(loc, defs, maximum_depth)
  else:
    ctx.exitpoint = loc
  snapshotter.take_snapshot("analyze:infer_types:post")
  ast = ctx.vm.compute_types(defs)
  ast = ctx.loader.resolve_ast(ast)
  if ctx.vm.has_unknown_wildcard_imports or any(
      a in defs for a in abstract_utils.DYNAMIC_ATTRIBUTE_MARKERS):
    if "__getattr__" not in ast:
      ast = pytd_utils.Concat(ast, ctx.loader.get_default_ast())
  # If merged with other if statement, triggers a ValueError: Unresolved class
  # when attempts to load from the protocols file
  if options.protocols:
    protocols_pytd = ctx.loader.import_name("protocols")
  else:
    protocols_pytd = None
  builtins_pytd = ctx.loader.concat_all()
  # Insert type parameters, where appropriate
  ast = ast.Visit(visitors.CreateTypeParametersForSignatures())
  if options.protocols:
    log.info("=========== PyTD to solve =============\n%s",
             pytd_utils.Print(ast))
    ast = convert_structural.convert_pytd(ast, builtins_pytd, protocols_pytd)
  elif not show_library_calls:
    log.info("Solving is turned off. Discarding call traces.")
    # Rename remaining "~unknown" to "?"
    ast = ast.Visit(visitors.RemoveUnknownClasses())
    # Remove "~list" etc.:
    ast = convert_structural.extract_local(ast)
  _maybe_output_debug(options, ctx.program)
  return ast, builtins_pytd


def _maybe_output_debug(options, program):
  """Maybe emit debugging output."""
  if options.output_cfg or options.output_typegraph:
    dot = debug.program_to_dot(program, set([]), bool(options.output_cfg))
    svg_file = options.output_cfg or options.output_typegraph
    with subprocess.Popen(
        ["/usr/bin/dot", "-T", "svg", "-o", svg_file],
        stdin=subprocess.PIPE, universal_newlines=True) as proc:
      (_, stderr) = proc.communicate(dot)
    if stderr:
      log.info("Failed to create %s: %s", svg_file, stderr)
  if options.output_debug:
    text = debug.program_to_text(program)
    if options.output_debug == "-":
      log.info("=========== Program Dump =============\n%s", text)
    else:
      with options.open_function(options.output_debug, "w") as fi:
        fi.write(text)
