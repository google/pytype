"""Module with common utilities used by other build and test scripts."""

from __future__ import print_function

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


def current_py_version():
  """Return the Python version under which this script is being run."""
  return "%d.%d" % (sys.version_info.major, sys.version_info.minor)


class PyVersionCache(object):
  """Utility class to manage the Python version cache."""

  VERSION_CACHE = os.path.join(OUT_DIR, ".python_version")

  @classmethod
  def read(cls):
    if os.path.exists(cls.VERSION_CACHE):
      with open(cls.VERSION_CACHE, "r") as f:
        return f.readline().strip()
    else:
      # There is no python version cache file during the very first run.
      return ""

  @classmethod
  def cache(cls):
    with open(cls.VERSION_CACHE, "w") as f:
      f.write(current_py_version())


def _clean_out_dir(msg):
  print(msg)
  for item in os.listdir(OUT_DIR):
    path = os.path.join(OUT_DIR, item)
    if os.path.isdir(path):
      shutil.rmtree(path)
    elif item not in ["README.md", ".gitignore"]:
      os.remove(path)


def get_module_and_log_file_from_result_msg(msg):
  if msg.startswith(FAILURE_MSG_PREFIX):
    _, mod_name, log_file = msg.split(RESULT_MSG_SEP)
    return mod_name, log_file
  if msg.startswith(PASS_MSG_PREFIX):
    _, mod_name = msg.split(RESULT_MSG_SEP)
    return mod_name, None
  return None, None


def failure_msg(mod_name, log_file):
  components = [FAILURE_MSG_PREFIX, mod_name]
  if log_file:
    components.append(log_file)
  return RESULT_MSG_SEP.join(components)


def pass_msg(mod_name):
  return RESULT_MSG_SEP.join([PASS_MSG_PREFIX, mod_name])


def run_cmd(cmd, cwd=None):
  process_options = {
      "stdout": subprocess.PIPE,
      "stderr": subprocess.STDOUT,
  }
  if cwd:
    process_options["cwd"] = cwd
  process = subprocess.Popen(cmd, **process_options)
  stdout, _ = process.communicate()
  if sys.version_info.major >= 3:
    # Popen.communicate returns a bytes object always.
    stdout = stdout.decode("utf-8")
  return process.returncode, stdout


def run_cmake(force_clean=False, log_output=False):
  """Run cmake in the 'out' directory."""
  current_version = current_py_version()
  if force_clean:
    _clean_out_dir("Force-cleaning 'out' directory.")
  elif PyVersionCache.read() != current_version:
    _clean_out_dir(
        "Previous Python version is not %s; cleaning 'out' directory.\n" %
        current_version)
  else:
    print("Running with the cached Python version; "
          "not cleaning 'out' directory.\n")

  if os.path.exists(os.path.join(OUT_DIR, "build.ninja")):
    # Run CMake if it was not already run. If CMake was already run, it
    # generates a build.ninja file in the "out" directory.
    print("Running CMake skipped ...\n")
    if log_output:
      with open(CMAKE_LOG, "w") as cmake_log:
        cmake_log.write("Running CMake was skipped.\n")
    return True

  print("Running CMake ...\n")
  cmd = ["cmake", PYTYPE_SRC_ROOT, "-G", "Ninja",
         "-DPython_ADDITIONAL_VERSIONS=%s" % current_version]
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
  # Cache the Python version for which the build files have been generated.
  PyVersionCache.cache()
  return True


def run_ninja(targets, fail_collector=None, fail_fast=False):
  """Run ninja over the list of specified targets.

  Arguments:
    targets: The list of test targets to run.
    fail_collector: A FailCollector object to collect failures.
    fail_fast: If True, abort at the first target failure.

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
  with open(NINJA_LOG, "w") as ninja_log:
    while True:
      line = process.stdout.readline()
      if not line:
        break
      if sys.version_info.major >= 3:
        # process.stdout.readline() always returns a 'bytes' object.
        line = line.decode("utf-8")
      ninja_log.write(line)
      if line.startswith(NINJA_FAILURE_PREFIX):
        # This is a failed ninja target.
        failed_targets.append(line[len(NINJA_FAILURE_PREFIX):].strip())
      modname, logfile = get_module_and_log_file_from_result_msg(line)
      if modname:
        print(line)
      if logfile:
        assert modname
        if fail_collector:
          fail_collector.add_failure(modname, logfile)
    if failed_targets:
      # For convenience, we will print the list of failed targets.
      summary_hdr = ">>> Detected Ninja target failures:"
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
