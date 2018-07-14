"""Module with common utilities used by other build and test scripts."""

from __future__ import print_function

import os
import shutil
import subprocess
import sys

PYTYPE_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PYTYPE_SRC_ROOT, "out")


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
