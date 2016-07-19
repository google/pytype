"""Configuration for pytype (mostly derived from the commandline args).

Various parts of pytype use the command-line options. This module packages the
options into an Options class.
"""

import logging
import optparse
import os
import subprocess


from pytype import utils


LOG_LEVELS = [logging.CRITICAL, logging.ERROR, logging.WARNING,
              logging.INFO, logging.DEBUG]


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
    argv = argv if argv is not None else [""]
    self._options, arguments = o.parse_args(argv)
    self.imports_map = None  # changed by main, using self.imports_info
    self._postprocess_options(o.option_list, arguments[1:])

  @classmethod
  def create(cls, **kwargs):
    self = cls(None)
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
    o.set_defaults(optimize=True)
    o.set_defaults(api=True)
    o.add_option(
        "-A", "--api", action="store_true",
        dest="api",
        help=("Analyze all functions and classes, "
              "also those not called from anywhere (default)."))
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
        "-d", "--disable", action="store",
        dest="disable", default=None,
        help=("Comma separated list of error names to ignore."))
    o.add_option(
        "--import_drop_prefixes", type="string", action="store",
        dest="import_drop_prefixes",
        default="",
        help=("List of prefixes to be dropped when resolving module names "
              "in import statements. The items are separated by '%s'. "
              "The individual items may contain '.'. "
              "The intended use case is for when you're running tests in "
              "a directory structure that starts below the root module in "
              "your module names. "
              "This option is incompatible with --imports_info.") % os.pathsep)
    o.add_option(
        "--imports_info", type="string", action="store",
        dest="imports_info", default=None,
        help=("Information for mapping import .pytd to files. "
              "This options is incompatible with --import_drop_prefixes "
              "and --pythonpath."))
    o.add_option(
        "-K", "--keep-unknowns", action="store_false",
        dest="solve_unknowns", default=True,
        help=("Keep 'unknown' classes generated during the first analysis "
              "pass."))
    o.add_option(
        "-m", "--main", action="store_true",
        dest="main_only",
        help=("Only analyze the main method and everything called from it"))
    o.add_option(
        "-M", "--module-name", action="store",
        dest="module_name", default=None,
        help=("Name of the module we're analyzing. E.g. 'foo.bar.mymodule'"))
    o.add_option(
        "--metrics", type="string", action="store",
        dest="metrics", default=None,
        help="Write a metrics report to the specified file.")
    o.add_option(
        "--no-native-builtins", action="store_false",
        dest="run_builtins", default=True,
        help=("Run the program without the native Python builtins preloaded."))
    o.add_option(
        "-N", "--no-cache-unknowns", action="store_false",
        dest="cache_unknowns", default=True,
        help="Do slower and more precise processing of unknown types.")
    o.add_option(
        "--no-skip-calls", action="store_false",
        dest="skip_repeat_calls", default=True,
        help=("Don't reuse the results of previous function calls."))
    o.add_option(
        "--nofail", action="store_true",
        dest="nofail", default=False,
        help=("Don't allow pytype to fail (for testing only)."))
    o.add_option(
        "-O", "--optimize", action="store_true",
        dest="optimize",
        help=("Optimize generated pytd (default)."))
    o.add_option(
        "-o", "--output", type="string", action="store",
        dest="output", default=None,
        help=("Output file (default: stdout). Only allowed if only one input."
              "Use '-' or '' for stdout."))
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
        "--python_exe", type="string", action="store",
        dest="python_exe", default=None,
        help=("Full path to a Python interpreter that is used to compile the "
              "source(s) to byte code. Can be \"HOST\" to use the same Python "
              "that is running pytype. If not specified, --python_version is "
              "used to create the name of an interpreter."))
    o.add_option(
        "-V", "--python_version", type="string", action="store",
        dest="python_version", default="2.7",
        help=("Python version to emulate (\"major.minor\", e.g. \"2.7\")"))
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
        "-Z", "--quick", action="store_true",
        dest="quick",
        help=("Only do an approximation."))
    o.add_option(
        "-R", "--raw", action="store_false",
        dest="optimize",
        help=("Do not optimize generated pytd"))
    o.add_option(
        "-r", "--reverse-operators", action="store_true",
        dest="reverse_operators", default=False,
        help=("Enable support for Python reverse "
              "operator overloading (__radd__ etc.)"))
    o.add_option(
        "-S", "--structural", action="store_true",
        dest="structural", default=False,
        help=("Analyze all functions and classes, also those not called from "
              "anywhere. Output the result in structural form."))
    o.add_option(
        "-T", "--no-typeshed", action="store_false",
        dest="typeshed", default=True,
        help=("Do not use typeshed to look up types in the Python stdlib. "
              "For testing."))
    o.add_option(
        "--no-report-errors", action="store_false",
        dest="report_errors", default=True,
        help=("Don't report errors. Only generate a .pyi."))
    o.add_option(
        # stored in basic_logging_level
        "-v", "--verbosity", type="int", action="store",
        dest="verbosity", default=1,
        help=("Set logging verbosity: "
              "-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug"))
    return o

  def _postprocess_options(self, option_list, arguments):
    """Store all options in self._option in self, possibly postprocessed.

    This will iterate through all options in self._options and make them
    attributes on our Options instance. If, for an option {name}, there is
    a _store_{name} method on this class, it'll call the method instead of
    storing the option directly. Additionally, it'll store the remaining
    command line arguments as "arguments" (or call _store_arguments).

    Args:
      option_list: Same as optparse.OptionParser().option_list.
      arguments: Other arguments on the command-line (i.e., things that don't
        start with '-')
    """
    # prepare function objects for topological sort:
    class Node(object):  # pylint: disable=g-wrong-blank-lines
      def __init__(self, name, processor):  # pylint: disable=g-wrong-blank-lines
        self.name = name
        self.processor = processor
    nodes = {
        opt.dest: Node(opt.dest, getattr(self, "_store_" + opt.dest, None))
        for opt in option_list if opt.dest
    }
    # The "arguments" attribute is not an option, but we treat it as one,
    # for dependency checking:
    nodes["arguments"] = Node("arguments",
                              getattr(self, "_store_arguments", None))
    for f in nodes.values():
      if f.processor:
        # option has a _store_{name} method
        dependencies = uses.lookup.get(f.processor.__name__)
        if dependencies:
          # that method has a @uses decorator
          f.incoming = tuple(nodes[use] for use in dependencies)

    # process the option list in the right order:
    for node in utils.topological_sort(nodes.values()):
      if node.name == "arguments":
        value = arguments
      else:
        value = getattr(self._options, node.name)
      if node.processor is not None:
        value = node.processor(value)
      else:
        setattr(self, node.name, value)

  def _store_verbosity(self, verbosity):
    if verbosity >= 0:
      if verbosity >= len(LOG_LEVELS):
        raise optparse.OptParseError("invalid --verbosity: %s" %
                                     self._options.verbosity)
      self.basic_logging_level = LOG_LEVELS[verbosity]
    else:
      # "verbosity=-1" can be used to disable all logging, so configure
      # logging accordingly.
      self.basic_logging_level = logging.CRITICAL + 1

  def _store_pythonpath(self, pythonpath):
    # Note that the below gives [""] for "", and ["x", ""] for "x:"
    # ("" is a valid entry to denote the current directory)
    self.pythonpath = pythonpath.split(os.pathsep)

  def _store_import_drop_prefixes(self, import_drop_prefixes):
    self.import_drop_prefixes = [
        p for p in import_drop_prefixes.split(os.pathsep) if p]

  def _store_python_version(self, python_version):
    self.python_version = tuple(map(int, python_version.split(".")))
    if len(self.python_version) != 2:
      raise optparse.OptionValueError(
          "--python_version must be <major>.<minor>: %r" % (
              self._options.python_version))
    if (3, 0) <= self.python_version <= (3, 3):
      # These have odd __build_class__ parameters, store co_code.co_name fields
      # as unicode, and don't yet have the extra qualname parameter to
      # MAKE_FUNCTION. Jumping through these extra hoops is not worth it, given
      # that typing.py isn't introduced until 3.5, anyway.
      raise optparse.OptParseError(
          "Python versions 3.0 - 3.3 are not supported. "
          "Use 3.4 and higher.")

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

  @uses(["import_drop_prefixes", "pythonpath"])
  def _store_imports_info(self, imports_info):
    if self.import_drop_prefixes:
      raise optparse.OptionConflictError(
          "Not allowed with --import_drop_prefixes", "imports_info")
    if self.pythonpath not in ([], [""]):
      raise optparse.OptionConflictError(
          "Not allowed with --pythonpath", "imports_info")
    self.imports_info = imports_info

  def _store_output(self, output):
    self.output = output

  @uses(["output", "check"])
  def _store_arguments(self, input_filenames):
    if len(input_filenames) > 1:
      if self.output:
        raise optparse.OptionValueError("-o only allowed for single input")
    self.src_out = []
    for item in input_filenames:
      split = tuple(item.split(os.pathsep))
      if len(split) == 1:
        if len(input_filenames) == 1 and self.output:
          # special case: For single input, you're allowed to use
          #   pytype myfile.py -o myfile.pyi
          self.src_out.append((item, self.output))
        else:
          self.src_out.append((item, None))
          self.check = True
      elif len(split) == 2:
        self.src_out.append(split)
      else:
        raise optparse.OptionValueError("Argument %r is not a pair of non-"
                                        "empty file names separated by %r" %
                                        (item, os.pathsep))
