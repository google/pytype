"""Configuration for pytype (mostly derived from the commandline args).

Various parts of pytype use the command-line options. This module packages the
options into a single object (Options class). This is very similar to a global
set of flags, except that it's one extra parameter to a number of objects.
"""

import logging
import optparse
import os
import subprocess


LOG_LEVELS = [logging.CRITICAL, logging.ERROR, logging.WARNING,
              logging.INFO, logging.DEBUG]

# Export the exception that main.py needs:
OptParseError = optparse.OptParseError


class Options(object):
  """Encapsulation of the command-line options.

  Attributes:
    _options:             The parsed options
    basic_logging_level:  Used to set logging.basicConfig(level=...)
    input_filenames:      The filenames from the command line
    imports_map:          dict of .py file name to corresponding pytd file.
                          These will have been created by separate invocations
                          of pytype -- that is, the situation is similar to
                          javac using .class files that have been created by
                          other invocations of javac.  imports_map may be None,
                          which is different from {} -- None means that there
                          was no imports_map whereas {} means it's empty.
    src_out:              List of (input,output) file name pairs
    The following are from the command-line options, but have been processesd
    into a list (or tuple):
      import_drop_prefixes
      python_version
      pythonpath
    The following are "inherited" from the command-line options as-is:
      api
      cache_unknowns
      check
      disable
      imports_info
      nofail
      optimize
      output
      output_cfg
      output_debug
      output_id
      output_typegraph
      pybuiltins_filename
      python_exe
      quick
      reverse_operators
      run_builtins
      skip_repeat_calls
      solve_unknowns
      structural
      typeshed
      verbosity
  """

  # List of attributes that aren't options on the command line:
  extra_attributes = ["basic_logging_level", "input_filenames", "imports_map",
                      "src_out"]


  def __init__(self, argv):
    """Parse and encapsulate the command-line options.

    Also sets up some basic logger configuration.

    Args:
      argv: typically sys.argv (argv[0] is the script pathname if known)
            Can be None for unit tests.

    Raises:
      optarse.OptParseError: bad option or input filenames.
    """
    for a in self.extra_attributes:
      setattr(self, a, None)
    # Allow argv to be None for unit tests
    self._parse_options([""] if argv is None else argv)
    self._process_options()
    self._initialize_filenames_and_output()

  @classmethod
  def create(cls, **kwargs):
    self = cls(None)
    self.tweak(**kwargs)
    return self

  def tweak(self, **kwargs):
    for k, v in kwargs.items():
      assert hasattr(self, k)  # Don't allow adding arbitrary junk
      setattr(self, k, v)

  def _parse_options(self, args):
    """Use optparse to parse command line options."""
    o = optparse.OptionParser(
        usage="usage: %prog [options] input1[:output1] [input2:output2 [...]]",
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
        "-c", "--check", action="store_true",
        dest="check",
        help=("Verify against existing \"output\" pytd files."))
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
        help=("TODO(pludemann): document this. "
              "Information for mapping import .pytd to files. "
              "This options is incompatible with --import_drop_prefixes."))
    o.add_option(
        "-K", "--keep-unknowns", action="store_false",
        dest="solve_unknowns", default=True,
        help=("Keep 'unknown' classes generated during the first analysis "
              "pass."))
    o.add_option(
        "-m", "--main", action="store_false",
        dest="api",
        help=("Only analyze the main method and everything called from it"))
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
# MOE:strip_line TODO(pludemann): remove when Bazel integration is done:
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
        "--output_id", type="string", action="store",
        dest="output_id",
        default="",
        help=("A string that's prepended to the contents of each output pyi, "
              "to identify what created it.  If empty (the default), "
              "nothing is prepended."))
    o.add_option(
        "--python_exe", type="string", action="store",
        dest="python_exe", default=None,
        # TODO(pludemann): pyc.py implements the following and might change.
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
        "-v", "--verbosity", type="int", action="store",
        dest="verbosity", default=1,
        help=("Set logging verbosity: "
              "-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug"))

    self._option_list = o.option_list
    self._options, self.input_filenames = o.parse_args(args)

  def _process_options(self):
    """Process the options from _parse_options."""
    unused_executable = self.input_filenames.pop(0)
    self.imports_map = None  # changed by main, using self.imports_info

    # Propagate all the underlying options. The net effect is the same as if:
    #    def __getattr__(self, name): return getattr(self._options, name)
    for opt in self._option_list:
      if opt.dest:
        setattr(self, opt.dest, getattr(self._options, opt.dest))

    # Post-process options, overriding a few

    if self.verbosity >= 0:
      if self.verbosity >= len(LOG_LEVELS):
        raise optparse.OptionError(self._options.verbosity, "verbosity")
      self.basic_logging_level = LOG_LEVELS[self.verbosity]
    else:
      # "verbosity=-1" can be used to disable all logging, so configure logging
      # accordingly.
      self.basic_logging_level = logging.CRITICAL + 1

    # Note that the below gives [""] for "", and ["x", ""] for "x:"
    # ("" is a valid entry to denote the current directory)
    self.pythonpath = self.pythonpath.split(os.pathsep)

    self.import_drop_prefixes = [
        p for p in self.import_drop_prefixes.split(os.pathsep) if p]

    self.python_version = tuple(map(int, self.python_version.split(".")))
    if len(self.python_version) != 2:
      raise optparse.OptionError("must be <major>.<minor>: %r" %
                                 self._options.python_version,
                                 "python_version")
    if (3, 0) <= self.python_version <= (3, 3):
      # These have odd __build_class__ parameters, store co_code.co_name fields
      # as unicode, and don't yet have the extra qualname parameter to
      # MAKE_FUNCTION. Jumping through these extra hoops is not worth it, given
      # that typing.py isn't introduced until 3.5, anyway.
      raise optparse.OptionError(
          "Python versions 3.0 - 3.3 are not supported. "
          "Use 3.4 and higher.", "python_version")
    if self.imports_info:
      if self.import_drop_prefixes:
        raise optparse.OptionConflictError(
            "Not allowed with --import_drop_prefixes", "imports_info")
      if self.pythonpath not in ([], [""]):
        raise optparse.OptionConflictError(
            "Not allowed with --pythonpath", "imports_info")

    if self.disable:
      self.disable = self.disable.split(",")
    else:
      self.disable = []

    if self.python_exe is None:
      exe = "python%d.%d" % self.python_version
      try:
        with open(os.devnull, "w") as null:
          subprocess.check_call(exe + " -V",
                                shell=True, stderr=null, stdout=null)
      except subprocess.CalledProcessError:
        raise optparse.OptionError("Need valid %s executable in $PATH" % exe,
                                   "V")

  def _initialize_filenames_and_output(self):
    """Figure out the input(s) and output(s).

    Raises:
      optarse.OptParseError: bad option or input filenames.
    """
    if len(self.input_filenames) > 1 and self.output:
      raise optparse.OptionError("only allowed for single input", "o")

    self.src_out = []
    for item in self.input_filenames:
      split = tuple(item.split(os.pathsep))
      if len(split) != 2:
        if len(split) == 1 and len(self.input_filenames) == 1:
          # special case: For single input, you're allowed to use
          #   pytype myfile.py -o myfile.pyi
          # and
          #   pytype -c myfile.py
          self.src_out.append((item, self.output))
        else:
          raise optparse.OptionValueError("Argument %r is not a pair of non-"
                                          "empty file names separated by %r" %
                                          (item, os.pathsep))
      else:
        self.src_out.append(split)
