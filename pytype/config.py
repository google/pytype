"""Configuration for pytype (mostly derived from the commandline args).

Various parts of pytype use the command-line options. This module packages the
options into an Options class.
"""

import argparse
import contextlib
import logging
import os
import sys

from pytype import errors
from pytype import imports_map_loader
from pytype import load_pytd
from pytype import utils
from pytype.typegraph import cfg_utils

import six


LOG_LEVELS = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO,
              logging.DEBUG]


uses = utils.AnnotatingDecorator()  # model relationship between options


class Options(object):
  """Encapsulation of the command-line options."""

  _HAS_DYNAMIC_ATTRIBUTES = True

  def __init__(self, argv_or_options):
    """Parse and encapsulate the command-line options.

    Also sets up some basic logger configuration.

    Args:
      argv_or_options: Either sys.argv[1:] (sys.argv[0] is the main script), or
                       already parsed options object returned by
                       ArgumentParser.parse_args.

    Raises:
      sys.exit(2): bad option or input filenames.
    """
    argument_parser = make_parser()
    if isinstance(argv_or_options, list):
      options = argument_parser.parse_args(argv_or_options)
    else:
      options = argv_or_options
    names = set(vars(options))
    try:
      Postprocessor(names, options, self).process()
    except PostprocessingError as e:
      argument_parser.error(utils.message(e))

  @classmethod
  def create(cls, input_filename=None, **kwargs):
    """Create options from kwargs."""
    argument_parser = make_parser()
    options = argument_parser.parse_args(
        [input_filename or "dummpy_input_file"])
    for k, v in kwargs.items():
      setattr(options, k, v)
    return cls(options)

  def tweak(self, **kwargs):
    for k, v in kwargs.items():
      assert hasattr(self, k)  # Don't allow adding arbitrary junk
      setattr(self, k, v)

  def __repr__(self):
    return "\n".join(["%s: %r" % (k, v)
                      for k, v in sorted(six.iteritems(self.__dict__))
                      if not k.startswith("_")])


def make_parser():
  """Use argparse to make a parser for command line options."""
  o = argparse.ArgumentParser(
      usage="%(prog)s [options] input",
      description="Infer/check types in a Python module")

  # Input files
  o.add_argument(
      "input", nargs="*", help="File to process")

  # Modes
  o.add_argument(
      "-C", "--check", action="store_true",
      dest="check", default=None,
      help=("Don't do type inference. Only check for type errors."))
  o.add_argument(
      "-o", "--output", type=str, action="store",
      dest="output", default=None,
      help=("Output file. Use '-' for stdout."))

  # Options
  # TODO(b/80098600): Change the typeshed test so we can get rid of this option.
  o.add_argument(
      "--python_exe", type=str, action="store",
      dest="python_exe", default=None,
      help=("Full path to a Python interpreter that is used to compile the "
            "source(s) to byte code. If not specified, --python_version is "
            "used to create the name of an interpreter."))
  add_basic_options(o)
  add_subtools(o)
  add_pickle_options(o)
  add_infrastructure_options(o)
  add_debug_options(o)
  return o


def add_basic_options(o):
  """Add basic options to the given parser."""
  o.add_argument(
      "-d", "--disable", action="store",
      dest="disable", default=None,
      help=("Comma separated list of error names to ignore."))
  o.add_argument(
      "--no-report-errors", action="store_false",
      dest="report_errors", default=True,
      help=("Don't report errors."))
  o.add_argument(
      "--protocols", action="store_true",
      dest="protocols", default=False,
      help="Experimental: solve unknown types to label with structural types.")
  o.add_argument(
      "-V", "--python_version", type=str, action="store",
      dest="python_version", default=None,
      help=("Python version to emulate (\"major.minor\", e.g. \"2.7\")"))
  o.add_argument(
      "--strict-import", action="store_true",
      dest="strict_import", default=False,
      help="Experimental: Only load submodules that are explicitly imported.")
  o.add_argument(
      "--check-variable-types", action="store_true",
      dest="check_variable_types", default=False,
      help="Experimental: Check variable values against their annotations.")
  o.add_argument(
      "--precise-return", action="store_true", dest="precise_return",
      default=False, help=("Experimental: Infer precise return types even for "
                           "invalid function calls."))


def add_subtools(o):
  """Add subtools to the given parser."""
  # TODO(rechen): These should be standalone tools.
  o = o.add_argument_group("subtools")
  o.add_argument(
      "--generate-builtins", action="store",
      dest="generate_builtins", default=None,
      help="Precompile builtins pyi and write to the given file.")
  o.add_argument(
      "--parse-pyi", action="store_true",
      dest="parse_pyi", default=False,
      help="Try parsing a PYI file. For testing of typeshed.")


def add_pickle_options(o):
  """Add options for using pickled pyi files to the given parser."""
  o = o.add_argument_group("pickle arguments")
  o.add_argument(
      "--pickle-output", action="store_true", default=False,
      dest="pickle_output",
      help=("Saves the ast representation of the inferred pyi as a pickled "
            "file. The value of this parameter is the destination filename "
            "for the pickled data."))
  o.add_argument(
      "--use-pickled-files", action="store_true", default=False,
      dest="use_pickled_files",
      help=("Use pickled pyi files instead of pyi files. This will check "
            "if a file 'foo.bar.pyi.pickled' is present next to "
            "'foo.bar.pyi' and load it instead. This will load the pickled "
            "file without further verification. Allowing untrusted pickled "
            "files into the code tree can lead to arbitrary code execution!"))
  o.add_argument(
      "--precompiled-builtins", action="store",
      dest="precompiled_builtins", default=None,
      help="Use the supplied file as precompiled builtins pyi.")


def add_infrastructure_options(o):
  """Add infrastructure options to the given parser."""
  o = o.add_argument_group("infrastructure arguments")
  o.add_argument(
      "--imports_info", type=str, action="store",
      dest="imports_map", default=None,
      help=("Information for mapping import .pyi to files. "
            "This options is incompatible with --pythonpath."))
  o.add_argument(
      "-M", "--module-name", action="store",
      dest="module_name", default=None,
      help=("Name of the module we're analyzing. For __init__.py files the "
            "package should be suffixed with '.__init__'. "
            "E.g. 'foo.bar.mymodule' and 'foo.bar.__init__'"))
  # TODO(b/68306233): Get rid of nofail.
  o.add_argument(
      "--nofail", action="store_true",
      dest="nofail", default=False,
      help=("Don't allow pytype to fail."))
  o.add_argument(
      "--return-success", action="store_true",
      dest="return_success", default=False,
      help="Report all errors but exit with a success code.")
  o.add_argument(
      "--output-errors-csv", type=str, action="store",
      dest="output_errors_csv", default=None,
      help=("Outputs the error contents to a csv file"))
  o.add_argument(
      "-P", "--pythonpath", type=str, action="store",
      dest="pythonpath", default="",
      help=("Directories for reading dependencies - a list of paths "
            "separated by '%s'. The files must have been generated "
            "by running pytype on dependencies of the file(s) "
            "being analyzed. That is, if an input .py file has an "
            "'import path.to.foo', and pytype has already been run "
            "with 'pytype path.to.foo.py -o "
            "$OUTDIR/path/to/foo.pyi', "
            "then pytype should be invoked with $OUTDIR in "
            "--pythonpath. This option is incompatible with "
            "--imports_info and --generate_builtins.") % os.pathsep)
  o.add_argument(
      "--touch", type=str, action="store",
      dest="touch", default=None,
      help="Output file to touch when exit status is ok.")
  o.add_argument(
      "-e", "--enable-only", action="store",
      dest="enable_only", default=None,
      help="Comma separated list of error names to enable checking for.")
  # TODO(rechen): --analyze-annotated and --quick would make more sense as
  # basic options but are currently used by pytype-all in a way that isn't
  # easily configurable.
  o.add_argument(
      "--analyze-annotated", action="store_true",
      dest="analyze_annotated", default=None,
      help=("Analyze methods with return annotations. By default, "
            "on for checking and off for inference."))
  o.add_argument(
      "-Z", "--quick", action="store_true",
      dest="quick", default=None,
      help=("Only do an approximation."))


def add_debug_options(o):
  """Add debug options to the given parser."""
  o = o.add_argument_group("debug arguments")
  o.add_argument(
      "--check_preconditions", action="store_true",
      dest="check_preconditions", default=False,
      help=("Enable checking of preconditions."))
  o.add_argument(
      "-m", "--main", action="store_true",
      dest="main_only", default=False,
      help=("Only analyze the main method and everything called from it"))
  o.add_argument(
      "--metrics", type=str, action="store",
      dest="metrics", default=None,
      help="Write a metrics report to the specified file.")
  o.add_argument(
      "--no-skip-calls", action="store_false",
      dest="skip_repeat_calls", default=True,
      help=("Don't reuse the results of previous function calls."))
  o.add_argument(
      "-T", "--no-typeshed", action="store_false",
      dest="typeshed", default=None,
      help=("Do not use typeshed to look up types in the Python stdlib. "
            "For testing."))
  o.add_argument(
      "--output-cfg", type=str, action="store",
      dest="output_cfg", default=None,
      help="Output control flow graph as SVG.")
  o.add_argument(
      "--output-debug", type=str, action="store",
      dest="output_debug", default=None,
      help="Output debugging data (use - to add this output to the log).")
  o.add_argument(
      "--output-typegraph", type=str, action="store",
      dest="output_typegraph", default=None,
      help="Output typegraph as SVG.")
  o.add_argument(
      "--profile", type=str, action="store",
      dest="profile", default=None,
      help="Profile pytype and output the stats to the specified file.")
  o.add_argument(
      "-v", "--verbosity", type=int, action="store",
      dest="verbosity", default=1,
      help=("Set logging verbosity: "
            "-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug"))
  o.add_argument(
      "-S", "--timestamp-logs", action="store_true",
      dest="timestamp_logs", default=None,
      help=("Add timestamps to the logs"))
  o.add_argument(
      "--verify-pickle", action="store_true", default=False,
      dest="verify_pickle",
      help=("Loads the generated PYI file and compares it with the abstract "
            "syntax tree written as pickled output. This will raise an "
            "uncaught AssertionError if the two ASTs are not the same. The "
            "option is intended for debugging."))
  o.add_argument(
      "--memory-snapshots", action="store_true", default=False,
      dest="memory_snapshots",
      help=("Enable tracemalloc snapshot metrics. Currently requires "
            "a version of Python with tracemalloc patched in."))
  o.add_argument(
      "--show-config", action="store_true",
      dest="show_config", default=None,
      help=("Display all config variables and exit."))
  o.add_argument(
      "--version", action="store_true",
      dest="version", default=None,
      help=("Display pytype version and exit."))
  # Timing out kills pytype with an error code. Useful for determining whether
  # pytype is fast enough to be enabled for a particular target.
  o.add_argument(
      "--timeout", type=int, action="store", dest="timeout", default=None,
      help="In seconds. Abort after the given time has elapsed.")
  o.add_argument(
      "--debug", action="store_true",
      dest="debug", default=None,
      help=("Flag used internally by some of pytype's subtools"))


class PostprocessingError(Exception):
  """Exception raised if Postprocessor.process() fails."""


class Postprocessor(object):
  """Postprocesses options read from the command line."""

  def __init__(self, names, input_options, output_options=None):
    self.names = names
    self.input_options = input_options
    # If output not specified, process in-place.
    self.output_options = output_options or input_options

  def process(self):
    """Postprocesses all options in self.input_options.

    This will iterate through all options in self.input_options and make them
    attributes on self.output_options. If, for an option {name}, there is
    a _store_{name} method on this class, it'll call the method instead of
    storing the option directly.
    """
    # Because of the mutual dependency between input and output, we process
    # them outside of the normal flow.
    if hasattr(self.input_options, "input"):
      self.input_options.input, output = self._parse_arguments(
          self.input_options.input)
    else:
      output = None
    if output and "output" in self.names:
      if getattr(self.input_options, "output", None):
        self.error("x:y notation not allowed with -o")
      self.input_options.output = output
    # prepare function objects for topological sort:
    class Node(object):  # pylint: disable=g-wrong-blank-lines
      def __init__(self, name, processor):  # pylint: disable=g-wrong-blank-lines
        self.name = name
        self.processor = processor
    nodes = {name: Node(name, getattr(self, "_store_" + name, None))
             for name in self.names}
    for f in nodes.values():
      if f.processor:
        # option has a _store_{name} method
        dependencies = uses.lookup.get(f.processor.__name__)
        if dependencies:
          # that method has a @uses decorator
          f.incoming = tuple(nodes[use] for use in dependencies)

    # process the option list in the right order:
    for node in cfg_utils.topological_sort(nodes.values()):
      value = getattr(self.input_options, node.name)
      if node.processor is not None:
        node.processor(value)
      else:
        setattr(self.output_options, node.name, value)

  def error(self, message, key=None):
    if key:
      message = "argument --%s: %s" % (key, message)
    raise PostprocessingError(message)

  @uses(["output"])
  def _store_check(self, check):
    if check is None:
      self.output_options.check = not self.output_options.output
    elif self.output_options.output:
      self.error("Not allowed with an output file", "check")
    else:
      self.output_options.check = check

  @uses(["output"])
  def _store_pickle_output(self, pickle_output):
    if pickle_output:
      if self.output_options.output is None:
        self.error("Can't use without --output", "pickle-output")
      elif not load_pytd.is_pickle(self.output_options.output):
        self.error("Must specify %s file for --output" % load_pytd.PICKLE_EXT,
                   "pickle-output")
    self.output_options.pickle_output = pickle_output

  @uses(["output", "pickle_output"])
  def _store_verify_pickle(self, verify_pickle):
    if not verify_pickle:
      self.output_options.verify_pickle = None
    elif not self.output_options.pickle_output:
      self.error("Can't use without --pickle-output", "verify-pickle")
    else:
      self.output_options.verify_pickle = self.output_options.output.replace(
          load_pytd.PICKLE_EXT, ".pyi")

  @uses(["input", "show_config", "pythonpath", "version"])
  def _store_generate_builtins(self, generate_builtins):
    """Store the generate-builtins option."""
    if generate_builtins:
      if self.output_options.input:
        self.error("Not allowed with an input file", "generate-builtins")
      if self.output_options.pythonpath != [""]:
        self.error("Not allowed with --pythonpath", "generate-builtins")
      # Set the default pythonpath to [] rather than [""]
      self.output_options.pythonpath = []
    elif (not self.output_options.input and
          not self.output_options.show_config and
          not self.output_options.version):
      self.error("Need a filename.")
    self.output_options.generate_builtins = generate_builtins

  @uses(["precompiled_builtins"])
  def _store_typeshed(self, typeshed):
    if typeshed is not None:
      self.output_options.typeshed = typeshed
    elif self.output_options.precompiled_builtins:
      # Typeshed is included in the builtins pickle.
      self.output_options.typeshed = False
    else:
      self.output_options.typeshed = True

  @uses(["timestamp_logs"])
  def _store_verbosity(self, verbosity):
    """Configure logging."""
    if not -1 <= verbosity < len(LOG_LEVELS):
      self.error("invalid --verbosity: %s" % verbosity)
    self.output_options.verbosity = verbosity

  def _store_pythonpath(self, pythonpath):
    # Note that the below gives [""] for "", and ["x", ""] for "x:"
    # ("" is a valid entry to denote the current directory)
    self.output_options.pythonpath = pythonpath.split(os.pathsep)

  def _store_python_version(self, python_version):
    """Configure the python version."""
    if python_version:
      if isinstance(python_version, str):
        self.output_options.python_version = utils.version_from_string(
            python_version)
      elif isinstance(python_version, int):
        self.output_options.python_version = utils.full_version_from_major(
            python_version)
      else:
        self.output_options.python_version = python_version
    else:
      self.output_options.python_version = sys.version_info[:2]
    if len(self.output_options.python_version) != 2:
      self.error(
          "--python_version must be <major>.<minor>: %r" % python_version)
    # Check that we have a version supported by pytype.
    utils.validate_version(self.output_options.python_version)

  def _store_disable(self, disable):
    if disable:
      self.output_options.disable = disable.split(",")
    else:
      self.output_options.disable = []

  @uses(["disable"])
  def _store_enable_only(self, enable_only):
    """Process the 'enable-only' option."""
    if enable_only:
      if self.output_options.disable:
        self.error("Only one of 'disable' or 'enable-only' can be specified.")
      self.output_options.disable = list(
          errors.get_error_names_set() - set(enable_only.split(",")))
    else:
      # We set the field to an empty list as clients using this postprocessor
      # expect a list.
      self.output_options.enable_only = []

  @uses(["python_version"])
  def _store_python_exe(self, python_exe):
    """Postprocess --python_exe."""
    if python_exe is None and utils.can_compile_bytecode_natively(
        self.output_options.python_version):
      # The user has not requested a custom exe and pytype does not need an exe
      # for bytecode compilation. Abort early to avoid extracting a large unused
      # exe into /tmp.
      self.output_options.python_exe = (None, None)
      return

    if python_exe is None:
      python_exe, flags = utils.get_python_exe(
          self.output_options.python_version)
      user_provided_exe = False
    else:
      if isinstance(python_exe, tuple):
        python_exe, flags = python_exe
      else:
        flags = []
      user_provided_exe = True
    python_exe_version = utils.get_python_exe_version(python_exe)
    if python_exe_version != self.output_options.python_version:
      if not user_provided_exe:
        err = ("Need a valid python%d.%d executable in $PATH" %
               self.output_options.python_version)
      elif python_exe_version:
        err = ("--python_exe version %d.%d does not match "
               "--python_version %d.%d" % (
                   python_exe_version + self.output_options.python_version))
      else:
        err = "Bad flag --python_exe: could not run %s" % python_exe
      self.error(err)
    self.output_options.python_exe = (python_exe, flags)

  @uses(["pythonpath", "output", "verbosity"])
  def _store_imports_map(self, imports_map):
    """Postprocess --imports_info."""
    if imports_map:
      if self.output_options.pythonpath not in ([], [""]):
        self.error("Not allowed with --pythonpath", "imports_info")

      with verbosity_from(self.output_options):
        self.output_options.imports_map = imports_map_loader.build_imports_map(
            imports_map, self.output_options.output)
    else:
      self.output_options.imports_map = None

  @uses(["output_cfg"])
  def _store_output_typegraph(self, output_typegraph):
    if self.output_options.output_cfg and output_typegraph:
      self.error(
          "Can output CFG or typegraph, but not both", "output-typegraph")
    self.output_options.output_typegraph = output_typegraph

  @uses(["report_errors"])
  def _store_output_errors_csv(self, output_errors_csv):
    if output_errors_csv and not self.output_options.report_errors:
      self.error("Not allowed with --no-report-errors", "output-errors-csv")
    self.output_options.output_errors_csv = output_errors_csv

  @uses(["input", "pythonpath"])
  def _store_module_name(self, module_name):
    if module_name is None:
      module_name = load_pytd.get_module_name(
          self.output_options.input, self.output_options.pythonpath)
    self.output_options.module_name = module_name

  @uses(["check"])
  def _store_analyze_annotated(self, analyze_annotated):
    if analyze_annotated is None:
      analyze_annotated = self.output_options.check
    self.output_options.analyze_annotated = analyze_annotated

  def _parse_arguments(self, arguments):
    """Parse the input/output arguments."""
    if len(arguments) > 1:
      self.error("Can only process one file at a time.")
    if not arguments:
      return None, None
    item, = arguments
    split = tuple(item.split(os.pathsep))
    if len(split) == 1:
      return item, None
    elif len(split) == 2:
      return split
    else:
      self.error("Argument %r is not a pair of non-empty file names "
                 "separated by %r" % (item, os.pathsep))


def _set_verbosity(verbosity, timestamp_logs):
  """Set the logging verbosity."""
  if verbosity >= 0:
    basic_logging_level = LOG_LEVELS[verbosity]
  else:
    # "verbosity=-1" can be used to disable all logging, so configure
    # logging accordingly.
    basic_logging_level = logging.CRITICAL + 1
  if logging.getLogger().handlers:
    # When calling pytype as a library, override the caller's logging level.
    logging.getLogger().setLevel(basic_logging_level)
  else:
    fmt = "%(levelname)s:%(name)s %(message)s"
    if timestamp_logs:
      fmt = "%(relativeCreated)f " + fmt
    logging.basicConfig(level=basic_logging_level, format=fmt)


@contextlib.contextmanager
def verbosity_from(options):
  """Sets the logging level to options.verbosity and restores it afterwards.

  If you directly call any of pytype's internal methods,
  like analyze.infer_types, use this contextmanager to set the logging
  verbosity. Consider using one of the top-level methods in pytype.io instead,
  which take care of this detail for you.

  Arguments:
    options: A config.Options object.

  Yields:
    Nothing.
  """
  level = logging.getLogger().getEffectiveLevel()
  _set_verbosity(options.verbosity, options.timestamp_logs)
  try:
    yield
  finally:
    logging.getLogger().setLevel(level)
