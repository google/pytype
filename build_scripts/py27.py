"""Utils to build Python-2.7 interpreter with type annotations backported.
"""
from __future__ import print_function

import argparse
import os
import sys

import build_utils

_BUILD_DIR = os.path.join(build_utils.OUT_DIR, "python27_build")
_INSTALL_DIR = os.path.join(build_utils.OUT_DIR, "python27")
_CPYTHON_SRC_DIR = os.path.join(build_utils.PYTYPE_SRC_ROOT, "cpython")


def _parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("--clobber", "-c", action="store_true", default=False,
                      help="Force clobber before building.")
  return parser.parse_args()


def _prepare_directories(clobber):
  if not os.path.exists(_BUILD_DIR):
    os.makedirs(_BUILD_DIR)
  if not os.path.exists(_INSTALL_DIR):
    os.makedirs(_INSTALL_DIR)
  if clobber:
    build_utils.clean_dir(_BUILD_DIR)
    build_utils.clean_dir(_INSTALL_DIR)


def _apply_patch():
  patch_file = os.path.join(build_utils.PYTYPE_SRC_ROOT, "2.7_patches",
                            "python_2_7_type_annotations.diff")
  return build_utils.run_cmd(["git", "apply", patch_file], cwd=_CPYTHON_SRC_DIR)


def _revert_patch():
  return build_utils.run_cmd(["git", "checkout", "--", "."],
                             cwd=_CPYTHON_SRC_DIR)


def _configure_build():
  config_script = os.path.join(_CPYTHON_SRC_DIR, "configure")
  return build_utils.run_cmd([config_script, "--prefix=%s" % _INSTALL_DIR],
                             cwd=_BUILD_DIR)


def _build():
  return build_utils.run_cmd(["make", "-j16"], cwd=_BUILD_DIR)


def _install():
  return build_utils.run_cmd(["make", "install"], cwd=_BUILD_DIR)


def build_backported_interpreter(clobber=False):
  print("Building Python-2.7 interpreter...\n")
  _prepare_directories(clobber)
  task_list = [
      (_apply_patch, "Applying type annotations patch"),
      (_configure_build, "Configuring CPython build"),
      (_build, "Building patched CPython interpreter"),
      (_install, "Installing the CPython interpreter"),
      (_revert_patch, "Reverting type annotations patch"),
  ]
  for task, task_info in task_list:
    print("Python-2.7 build step: %s... " % task_info, end='')
    returncode, _ = task()
    if returncode != 0:
      print("FAILED\n" % task_info)
      return returncode
    print("DONE")
  print("")  # An empty line at the end of successfull build.
  print("Python-2.7 interpreter built succesfully!\n")
  return 0


def main():
  options = _parse_args()
  sys.exit(build_backported_interpreter(options.clobber))


if __name__ == "__main__":
  main()
