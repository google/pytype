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
GEN_FILE_LIST = [
    "lexer.lex.cc",
    "location.hh",
    "parser.tab.cc",
    "parser.tab.hh",
    "position.hh",
    "stack.hh",
]


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


def run_cmd(cmd, cwd=None):
  process_options = {
      "stdout": subprocess.PIPE,
      "stderr": subprocess.STDOUT,
  }
  if cwd:
    process_options["cwd"] = cwd
  process = subprocess.Popen(cmd, **process_options)
  stdout, _ = process.communicate()
  return process.returncode, stdout


def run_cmake(force_clean=False):
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
    return True

  print("Running CMake ...\n")
  cmd = ["cmake", PYTYPE_SRC_ROOT, "-G", "Ninja",
         "-DPython_ADDITIONAL_VERSIONS=%s" % current_version]
  returncode, stdout = run_cmd(cmd, cwd=OUT_DIR)
  # Cache the Python version for which the build files have been generated.
  PyVersionCache.cache()
  if returncode != 0:
    print("Running %s failed:\n%s" % (cmd, stdout))
    return False
  return True


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
