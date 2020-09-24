"""Module with common utilities used by other build and test scripts."""

from __future__ import print_function

import json
import os
import shutil
import subprocess
import sys

PYTYPE_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PYTYPE_SRC_ROOT, "out")
SRC_PYI_DIR = os.path.join(PYTYPE_SRC_ROOT, "pytype", "pyi")
OUT_PYI_DIR = os.path.join(OUT_DIR, "pytype", "pyi")
CMAKE_LOG = os.path.join(OUT_DIR, "cmake.log")
NINJA_LOG = os.path.join(OUT_DIR, "ninja.log")
GEN_FILE_LIST = [
    "lexer.lex.cc",
    "location.hh",
    "parser.tab.cc",
    "parser.tab.hh",
    "position.hh",
    "stack.hh",
]

NINJA_FAILURE_PREFIX = "FAILED: "
FAILURE_MSG_PREFIX = ">>> FAIL"
PASS_MSG_PREFIX = ">>> PASS"
RESULT_MSG_SEP = " - "
_NOT_A_MSG = 0
_NINJA_FAILURE_MSG = 1
_TEST_MODULE_FAIL_MSG = 2
_TEST_MODULE_PASS_MSG = 3


def current_py_version():
  """Return the Python version under which this script is being run."""
  return "%d.%d" % (sys.version_info.major, sys.version_info.minor)


def build_script(base_name):
  """Return the full path to a script in the 'build_scripts' directory."""
  return os.path.join(PYTYPE_SRC_ROOT, "build_scripts", base_name)


class BuildConfig(object):
  """Utility class to create and manage the build config cache."""

  BUILD_CONFIG_CACHE = os.path.join(OUT_DIR, ".build_config.json")

  def __init__(self, **kwargs):
    self.py_version = kwargs.get("py_version")
    self.build_type = kwargs.get("build_type")

  def save_to_cache_file(self):
    with open(self.BUILD_CONFIG_CACHE, "w") as f:
      json.dump(
          {"py_version": self.py_version, "build_type": self.build_type}, f)

  def __eq__(self, other):
    return all([self.py_version == other.py_version,
                self.build_type == other.build_type])

  def __ne__(self, other):
    return any([self.py_version != other.py_version,
                self.build_type != other.build_type])

  @classmethod
  def current_build_config(cls, debug):
    return BuildConfig(**{
        "py_version": current_py_version(),
        "build_type": "debug" if debug else "None"
    })

  @classmethod
  def read_cached_config(cls):
    if os.path.exists(cls.BUILD_CONFIG_CACHE):
      with open(cls.BUILD_CONFIG_CACHE, "r") as f:
        return BuildConfig(**json.load(f))
    else:
      # There is no python version cache file during the very first run.
      return BuildConfig(**{})


def clean_dir(dir_path, exclude_file_list=None):
  exclude_list = exclude_file_list or []
  for item in os.listdir(dir_path):
    path = os.path.join(dir_path, item)
    if os.path.isdir(path):
      shutil.rmtree(path)
    elif item not in exclude_list:
      os.remove(path)


def _clean_out_dir(msg):
  print(msg)
  clean_dir(OUT_DIR, ["README.md", ".gitignore"])


def parse_ninja_output_line(line):
  if line.startswith(NINJA_FAILURE_PREFIX):
    return _NINJA_FAILURE_MSG, None, None
  elif line.startswith(FAILURE_MSG_PREFIX):
    components = line.split(RESULT_MSG_SEP)
    log_file = components[2] if len(components) == 3 else None
    return _TEST_MODULE_FAIL_MSG, components[1], log_file
  elif line.startswith(PASS_MSG_PREFIX):
    _, mod_name = line.split(RESULT_MSG_SEP)
    return _TEST_MODULE_PASS_MSG, mod_name, None
  else:
    return _NOT_A_MSG, None, None


def failure_msg(mod_name, log_file):
  components = [FAILURE_MSG_PREFIX, mod_name]
  if log_file:
    components.append(log_file)
  return RESULT_MSG_SEP.join(components)


def pass_msg(mod_name):
  return RESULT_MSG_SEP.join([PASS_MSG_PREFIX, mod_name])


def run_cmd(cmd, cwd=None, pipe=True):
  process_options = {}
  if pipe:
    process_options = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
    }
  if cwd:
    process_options["cwd"] = cwd
  process = subprocess.Popen(cmd, **process_options)
  stdout, _ = process.communicate()
  if pipe and sys.version_info.major >= 3:
    # Popen.communicate returns a bytes object always.
    stdout = stdout.decode("utf-8")
  return process.returncode, stdout


def run_cmake(force_clean=False, log_output=False, debug_build=False):
  """Run cmake in the 'out' directory."""
  current_config = BuildConfig.current_build_config(debug_build)
  if force_clean:
    _clean_out_dir("Force-cleaning 'out' directory.")
  elif BuildConfig.read_cached_config() != current_config:
    _clean_out_dir(
        "Previous build config was different; cleaning 'out' directory.\n")
  else:
    print("Running with build config same as cached build config; "
          "not cleaning 'out' directory.\n")

  if os.path.exists(os.path.join(OUT_DIR, "build.ninja")):
    # Run CMake if it was not already run. If CMake was already run, it
    # generates a build.ninja file in the "out" directory.
    msg = "Running CMake skipped as the build.ninja file is present ...\n"
    print(msg)
    if log_output:
      with open(CMAKE_LOG, "w") as cmake_log:
        cmake_log.write(msg)
    return True

  print("Running CMake ...\n")
  cmd = ["cmake", PYTYPE_SRC_ROOT, "-G", "Ninja",
         "-DPython_ADDITIONAL_VERSIONS=%s" % current_config.py_version]
  if debug_build:
    cmd.append("-DCMAKE_BUILD_TYPE=Debug")
  returncode, stdout = run_cmd(cmd, cwd=OUT_DIR)
  # Print the full CMake output to stdout. It is not a lot that it would
  # clutter the output, and also gives information about the Python version
  # found etc.
  print(stdout)
  if log_output:
    with open(CMAKE_LOG, "w") as cmake_log:
      cmake_log.write(stdout)
  if returncode != 0:
    print(">>> FAILED: CMake command '%s'" % " ".join(cmd))
    if log_output:
      print(">>>         Full CMake output is available in '%s'." % CMAKE_LOG)
    return False
  # Cache the config for which the build files have been generated.
  current_config.save_to_cache_file()
  return True


class FailCollector(object):
  """A class to collect failures."""

  def __init__(self):
    self._failures = []

  def add_failure(self, mod_name, log_file):
    self._failures.append((mod_name, log_file))

  def print_report(self, verbose):
    num_failures = len(self._failures)
    if num_failures == 0:
      return
    print("\n%d test module(s) failed: \n" % num_failures)
    for mod_name, log_file in self._failures:
      msg = "** %s" % mod_name
      if log_file:
        msg += " - %s" % log_file
      print(msg)
      if log_file and verbose:
        with open(log_file.strip(), 'r') as f:
          print(f.read(), file=sys.stderr)


def run_ninja(targets, fail_collector=None, fail_fast=False, verbose=False):
  """Run ninja over the list of specified targets.

  Arguments:
    targets: The list of targets to run.
    fail_collector: A FailCollector object to collect failures.
    fail_fast: If True, abort at the first target failure.
    verbose: If True, print verbose output.

  Returns:
    True if no target fails. False, otherwise.
  """
  # The -k option to ninja, set to a very high value, makes it run until it
  # detects all failures. So, we set it to a high value unless |fail_fast| is
  # True.
  cmd = ["ninja", "-k", "1" if fail_fast else "100000"] + targets
  process = subprocess.Popen(cmd, cwd=OUT_DIR,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  failed_targets = []
  # When verbose output is requested, test failure logs are printed to stderr.
  # However, sometimes a test fails without generating a log, in which case we
  # need to print the ninja build output to see what happened.
  print_if_verbose = False
  with open(NINJA_LOG, "w") as ninja_log:
    while True:
      line = process.stdout.readline()
      if not line:
        break
      if sys.version_info.major >= 3:
        # process.stdout.readline() always returns a 'bytes' object.
        line = line.decode("utf-8")
      ninja_log.write(line)
      msg_type, modname, logfile = parse_ninja_output_line(line)
      if msg_type == _NINJA_FAILURE_MSG:
        # This is a failed ninja target.
        failed_targets.append(line[len(NINJA_FAILURE_PREFIX):].strip())
        print_if_verbose = True
      if msg_type == _TEST_MODULE_PASS_MSG or msg_type == _TEST_MODULE_FAIL_MSG:
        print(line)
        if msg_type == _TEST_MODULE_FAIL_MSG:
          fail_collector.add_failure(modname, logfile)
        print_if_verbose = False
      if verbose and print_if_verbose:
        print(line.rstrip())
    if failed_targets:
      # For convenience, we will print the list of failed targets.
      summary_hdr = ">>> Found Ninja target failures (includes test failures):"
      print("\n" + summary_hdr)
      ninja_log.write("\n" + summary_hdr + "\n")
      for t in failed_targets:
        target = "    - %s" % t
        print(target)
        ninja_log.write(target + "\n")
  process.wait()
  if process.returncode == 0:
    return True
  else:
    # Ninja output can be a lot. Printing it here will clutter the output of
    # this script. So, just tell the user how to repro the error.
    print(">>> FAILED: Ninja command '%s'." % " ".join(cmd))
    print(">>>         Run it in the 'out' directory to reproduce.")
    print(">>>         Full Ninja output is available in '%s'." % NINJA_LOG)
    print(">>>         Failing test modules (if any) will be reported below.")
    return False


def generate_files():
  """Run flex and bison to produce the parser .cc and .h files.

  Returns:
    None upon success, otherwise an error message.
  """
  if not run_cmake(force_clean=True):
    return "Running CMake failed!"
  ninja_cmd = ["ninja", "pytype.pyi.parser_gen", "pytype.pyi.lexer"]
  print("Building flex and bison outputs ...\n")
  returncode, stdout = run_cmd(ninja_cmd, cwd=OUT_DIR)
  if returncode != 0:
    return "Error generating the Flex and Bison outputs:\n%s" % stdout
  # Copy the generated files into the source tree.
  for gen_file in GEN_FILE_LIST:
    print("Copying %s to source tree ...\n" % gen_file)
    shutil.copy(os.path.join(OUT_PYI_DIR, gen_file),
                os.path.join(SRC_PYI_DIR, gen_file))
  return None


def clean_generated_files():
  for gen_file in GEN_FILE_LIST:
    print("Deleting %s from source tree ...\n" % gen_file)
    os.remove(os.path.join(SRC_PYI_DIR, gen_file))
