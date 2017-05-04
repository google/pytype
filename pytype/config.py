"""Configuration for pytype (mostly derived from the commandline args).

Various parts of pytype use the command-line options. This module packages the
options into an Options class.
"""

import logging
import optparse
import os
import subprocess


from pytype import imports_map_loader
from pytype import utils
from pytype.pytd import cfg


LOG_LEVELS = [logging.CRITICAL, logging.ERROR, logging.WARNING,
              logging.INFO, logging.DEBUG, logging.DEBUG - 1]


OptParseError = optparse.OptParseError  # used by main.py


uses = utils.AnnotatingDecorator()  # model relationship between options


class Options(object):
  """Encapsulation of the command-line options."""

  def __init__(self, argv):
    """Parse and encapsulate the command-line options.

    Also sets up some basic logger configuration.

    Args:
      argv: sys.argv (argv[0] is the main script). None for unit tests.

    Raises:
      optarse.OptParseError: bad option or input filenames.
    """
    o = self._options()
    self._options, arguments = o.parse_args(argv)
    self._options.input, output = _parse_arguments(arguments[1:])
    if output:
      if self._options.output:
        raise optparse.OptionValueError("x:y notation not allowed with -o")
      self._options.output = output
    names = {opt.dest for opt in o.option_list if opt.dest}
    names.add("input")
    self._postprocess_options(names)

  @classmethod
  def create(cls, **kwargs):
    """Create dummy options for testing."""
    self = cls(["", "dummy_input_file"])
    self.tweak(**kwargs)
    return self

  def tweak(self, **kwargs):
    for k, v in kwargs.items():
      assert hasattr(self, k)  # Don't allow adding arbitrary junk
      setattr(self, k, v)

  def _options(self):
    """Use optparse to parse command line options."""
    o = optparse.OptionParser(
        usage=("Usage: %prog [options] "
               "file1.py[:file1.pyi] [file2.py:file2.pyi [...]]"),
        description="Infer/check types in a Python module")
    o.add_option(
        "-B", "--builtins", type="string", action="store",
        dest="pybuiltins_filename", default=None,
        help=("Use user-supplied custom definition of __builtin__.py "
              "(for debugging). This should be an absolute file name; "
              "if it is not an absolute file name, it is resolved using "
              "--pythonpath. "
              "The default resolves to pytd/builtins/__builtin__.py. "
              "Note that this does not affect the PyTD for builtins, which "
              "is always in pytd/builtins/__builtin__.pytd."))
    o.add_option(
        "-C", "--check", action="store_true",
        dest="check",
        help=("Don't do type inference. Only check for type errors."))
    o.add_option(
        "--check_preconditions", action="store_true",
        dest="check_preconditions", default=False,
        help=("Enable checking of preconditions."))
    o.add_option(
        "-d", "--disable", action="store",
        dest="disable", default=None,
        help=("Comma separated list of error names to ignore."))
    o.add_option(
        "--generate-builtins", action="store",
        dest="generate_builtins", default=None,
        help="Precompile builtins pytd and write to the given file.")
    o.add_option(
        "--output-pickled", action="store",
        dest="output_pickled",
        help=("Saves the ast representation of the inferred pyi as a pickled "
              "file. The value of this parameter is the destination filename "
              "for the pickled data."))
    o.add_option(
        "--imports_info", type="string", action="store",
        dest="imports_map", default=None,
        help=("Information for mapping import .pytd to files. "
              "This options is incompatible with --pythonpath."))
    o.add_option(
        "-m", "--main", action="store_true",
        dest="main_only", default=False,
        help=("Only analyze the main method and everything called from it"))
    o.add_option(
        "-M", "--module-name", action="store",
        dest="module_name", default=None,
        help=("Name of the module we're analyzing. E.g. 'foo.bar.mymodule'"))
    o.add_option(
        "-t", "--target-name", action="store",
        dest="target_name", default=None,
        help=("Description of the module we're analyzing. "
              "Displayed for import errors."))
    o.add_option(
        "--metrics", type="string", action="store",
        dest="metrics", default=None,
        help="Write a metrics report to the specified file.")
    o.add_option(
        "-N", "--no-cache-unknowns", action="store_false",
        dest="cache_unknowns", default=True,
        help="Do slower and more precise processing of unknown types.")
    o.add_option(
        "--no-native-builtins", action="store_false",
        dest="run_builtins", default=True,
        help=("Run the program without the native Python builtins preloaded."))
    o.add_option(
        "--no-report-errors", action="store_false",
        dest="report_errors", default=True,
        help=("Don't report errors. Only generate a .pyi."))
    o.add_option(
        "--no-skip-calls", action="store_false",
        dest="skip_repeat_calls", default=True,
        help=("Don't reuse the results of previous function calls."))
    o.add_option(
        "-T", "--no-typeshed", action="store_false",
        dest="typeshed", default=True,
        help=("Do not use typeshed to look up types in the Python stdlib. "
              "For testing."))
    o.add_option(
        "--strict-attr-checking", action="store_true",
        dest="strict_attr_checking", default=False,
        help=("Complain about attribute errors even if only some of the"
              "options of a variable don't have the attribute."))
    o.add_option(
        "--nofail", action="store_true",
        dest="nofail", default=False,
        help=("Don't allow pytype to fail."))
    o.add_option(
        "-o", "--output", type="string", action="store",
        dest="output", default=None,
        help=("Output file. Use '-' or '' for stdout."))
    o.add_option(
        "--output-errors-csv", type="string", action="store",
        dest="output_errors_csv", default=None,
        help=("Outputs the error contents to a csv file"))
    o.add_option(
        "--output-cfg", type="string", action="store",
        dest="output_cfg", default=None,
        help="Output control flow graph as SVG.")
    o.add_option(
        "--output-debug", type="string", action="store",
        dest="output_debug", default=None,
        help="Output debugging data (use - to add this output to the log).")
    o.add_option(
        "--output-typegraph", type="string", action="store",
        dest="output_typegraph", default=None,
        help="Output typegraph as SVG.")
    o.add_option(
        "--profile", type="string", action="store",
        dest="profile", default=None,
        help="Profile pytype and output the stats to the specified file.")
    o.add_option(
        "--precompiled-builtins", action="store",
        dest="precompiled_builtins", default=None,
        help="Use the supplied file as precompiled builtins pytd.")
    o.add_option(
        "--python_exe", type="string", action="store",
        dest="python_exe", default=None,
        help=("Full path to a Python interpreter that is used to compile the "
              "source(s) to byte code. Can be \"HOST\" to use the same Python "
              "that is running pytype. If not specified, --python_version is "
              "used to create the name of an interpreter."))
    o.add_option(
        "--use-pickled-files", action="store_true", default=False,
        dest="use_pickled_files",
        help=("Use pickled pyi files instead of pyi files. This will check "
              "if a file 'foo.bar.pyi.pickled' is present next to "
              "'foo.bar.pyi' and load it instead. This will load the pickled "
              "file without further verification. Allowing untrusted pickled "
              "files into the code tree can lead to arbitrary code execution!"))
    o.add_option(
        "-P", "--pythonpath", type="string", action="store",
        dest="pythonpath", default="",
        help=("Directories for reading dependencies - a list of paths "
              "separated by '%s'. The files must have been generated "
              "by running pytype on dependencies of the file(s) "
              "being analyzed. That is, if an input .py file has an "
              "'import path.to.foo', and pytype has already been run "
              "with 'pytype path.to.foo.py -o "
              "$OUTDIR/path/to/foo.pytd', "  # TODO(kramm): Change to .pyi
              "then pytype should be invoked with $OUTDIR in "
              "--pythonpath. This option is incompatible with "
              "--imports_info.") % os.pathsep)
    o.add_option(
        "--touch", type="string", action="store",
        dest="touch", default=None,
        help="Output file to touch when exit status is ok.")
    o.add_option(
        "-V", "--python_version", type="string", action="store",
        dest="python_version", default="2.7",
        help=("Python version to emulate (\"major.minor\", e.g. \"2.7\")"))
    o.add_option(
        # Not stored, just used to configure logging.
        "-v", "--verbosity", type="int", action="store",
        dest="verbosity", default=1,
        help=("Set logging verbosity: "
              "-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug"))
    o.add_option(
        "--verify-pickle", action="store_true", default=False,
        dest="verify_pickle",
        help=("Loads the generated PYI file and compares it with the abstract "
              "syntax tree written as pickled output. This will raise an "
              "uncaught AssertionError if the two ASTs are not the same. The "
              "option is intended for debugging."))
    o.add_option(
        "-Z", "--quick", action="store_true",
        dest="quick",
        help=("Only do an approximation."))
    o.add_option(
        "--memory-snapshots", action="store_true", default=False,
        dest="memory_snapshots",
        help=("Enable tracemalloc snapshot metrics. Currently requires "
              "a version of Python with tracemalloc patched in."))
    return o

  def _postprocess_options(self, names):
    """Store all options in self._options in self, possibly postprocessed.

    This will iterate through all options in self._options and make them
    attributes on our Options instance. If, for an option {name}, there is
    a _store_{name} method on this class, it'll call the method instead of
    storing the option directly. Additionally, it'll store the remaining
    command line arguments as "arguments" (or call _store_arguments).

    Args:
      names: The names of the options.
    """
    # prepare function objects for topological sort:
    class Node(object):  # pylint: disable=g-wrong-blank-lines
      def __init__(self, name, processor):  # pylint: disable=g-wrong-blank-lines
        self.name = name
        self.processor = processor
    nodes = {name: Node(name, getattr(self, "_store_" + name, None))
             for name in names}
    for f in nodes.values():
      if f.processor:
        # option has a _store_{name} method
        dependencies = uses.lookup.get(f.processor.__name__)
        if dependencies:
          # that method has a @uses decorator
          f.incoming = tuple(nodes[use] for use in dependencies)

    # process the option list in the right order:
    for node in utils.topological_sort(nodes.values()):
      value = getattr(self._options, node.name)
      if node.processor is not None:
        node.processor(value)
      else:
        setattr(self, node.name, value)

  @uses(["output"])
  def _store_check(self, check):
    if check is None:
      self.check = not self.output
    elif self.output:
      raise optparse.OptionConflictError("Not allowed with an output file",
                                         "check")
    else:
      self.check = check

  def _store_strict_attr_checking(self, b):
    if b:
      cfg.APPROXIMATE = False
    self.strict_attr_checking = b

  @uses(["input"])
  def _store_generate_builtins(self, generate_builtins):
    if generate_builtins:
      if self.input:
        raise optparse.OptionConflictError("Not allowed with an input file",
                                           "generate-builtins")
    elif not self.input:
      raise optparse.OptParseError("Need a filename.")
    self.generate_builtins = generate_builtins

  @uses(["module_name"])
  def _store_read_pyi_save_pickle(self, read_pyi_save_pickle):
    if read_pyi_save_pickle and not self.module_name:
      raise OptParseError(
          "--module-name must be set, for pickling and saving an AST.")
    self.read_pyi_save_pickle = read_pyi_save_pickle

  def _store_verbosity(self, verbosity):
    """Configure logging."""
    if verbosity >= 0:
      if verbosity >= len(LOG_LEVELS):
        raise optparse.OptParseError("invalid --verbosity: %s" % verbosity)
      basic_logging_level = LOG_LEVELS[verbosity]
    else:
      # "verbosity=-1" can be used to disable all logging, so configure
      # logging accordingly.
      basic_logging_level = logging.CRITICAL + 1
    utils.set_logging_level(basic_logging_level)

  def _store_pythonpath(self, pythonpath):
    # Note that the below gives [""] for "", and ["x", ""] for "x:"
    # ("" is a valid entry to denote the current directory)
    self.pythonpath = pythonpath.split(os.pathsep)

  def _store_python_version(self, python_version):
    self.python_version = tuple(map(int, python_version.split(".")))
    if len(self.python_version) != 2:
      raise optparse.OptionValueError(
          "--python_version must be <major>.<minor>: %r" % python_version)
    if (3, 0) <= self.python_version <= (3, 3):
      # These have odd __build_class__ parameters, store co_code.co_name fields
      # as unicode, and don't yet have the extra qualname parameter to
      # MAKE_FUNCTION. Jumping through these extra hoops is not worth it, given
      # that typing.py isn't introduced until 3.5, anyway.
      raise optparse.OptParseError(
          "Python versions 3.0 - 3.3 are not supported. "
          "Use 3.4 and higher.")
    if self.python_version > (3, 6):
      # We have an explicit per-minor-version mapping in opcodes.py
      raise optparse.OptParseError(
          "Python versions > 3.6 are not yet supported.")

  def _store_disable(self, disable):
    if disable:
      self.disable = disable.split(",")
    else:
      self.disable = []

  @uses(["python_version"])
  def _store_python_exe(self, python_exe):
    """Postprocess --python_exe."""
    if python_exe is None:
      python_exe = "python%d.%d" % self.python_version
      try:
        with open(os.devnull, "w") as null:
          subprocess.check_call(python_exe + " -V",
                                shell=True, stderr=null, stdout=null)
      except subprocess.CalledProcessError:
        raise optparse.OptParseError("Need valid %s executable in $PATH" %
                                     python_exe)
    self.python_exe = python_exe

  @uses(["pythonpath", "output", "verbosity"])
  def _store_imports_map(self, imports_map):
    """Postprocess --imports_info."""
    if imports_map:
      if self.pythonpath not in ([], [""]):
        raise optparse.OptionConflictError(
            "Not allowed with --pythonpath", "imports_info")

      self.imports_map = imports_map_loader.build_imports_map(
          imports_map, self.output)
    else:
      self.imports_map = None

  @uses(["report_errors"])
  def _store_output_errors_csv(self, output_errors_csv):
    if output_errors_csv and not self.report_errors:
      raise optparse.OptionConflictError("Not allowed with --no-report-errors",
                                         "output-errors-csv")
    self.output_errors_csv = output_errors_csv


def _parse_arguments(arguments):
  if len(arguments) > 1:
    raise optparse.OptionValueError("Can only process one file at a time.")
  if not arguments:
    return None, None
  item, = arguments
  split = tuple(item.split(os.pathsep))
  if len(split) == 1:
    return item, None
  elif len(split) == 2:
    return split
  else:
    raise optparse.OptionValueError("Argument %r is not a pair of non-"
                                    "empty file names separated by %r" %
                                    (item, os.pathsep))
