#! /usr/bin/python
"""A script to push a new Pytype release to PyPI.

This script assumes that you have twine and pandoc installed. The easiest way to
run this script is to run from inside of a virtualenv after "pip" installing
"twine". Also, this virtualenv should not have pytype installed already.

USAGE:

$> python release.py --mode=<TEST|RELEASE>

If mode is "TEST", then the release will be pushed to testpypi. If the mode is
"RELEASE", then the release is pushed to pypi.
"""

from __future__ import print_function

import argparse
import os
import shutil
import sys
import tempfile

import build_utils

from six.moves import input

TEST_MODE = "TEST"
RELEASE_MODE = "RELEASE"


class ReleaseError(Exception):

  def __init__(self, msg):
    super(ReleaseError, self).__init__()
    self.msg = msg


def parse_args():
  """Parse and return the command line args."""
  allowed_modes = (TEST_MODE, RELEASE_MODE)
  parser = argparse.ArgumentParser()
  parser.add_argument(
      "-m", "--mode", type=str, default="%s" % TEST_MODE,
      help="Specify if the release should be uploaded to pypi or testpyi. Can "
           "take a value of %s or %s" % allowed_modes)
  args = parser.parse_args()
  if args.mode not in allowed_modes:
    sys.exit("Invalid --mode option. Should be one of %s" % allowed_modes)
  return args


def verify_no_pytype_installation_exists():
  try:
    import pytype as _  # pylint: disable=g-import-not-at-top
  except ImportError:
    return  # This is what we want - that Pytype does not already exist.
  sys.exit("ERROR: Pytype installation detected; Run this script from inside "
           "a virtualenv without a pytype installation.")


def verify_pypirc_exists():
  pypirc_path = os.path.join(os.path.expanduser("~"), ".pypirc")
  if not os.path.exists(pypirc_path):
    sys.exit("ERROR: '.pypirc' file not found.")


def verify_description_rst_is_up_to_date():
  """If the DESCRIPTION.rst file is not up to date, abort."""
  temp_dir = tempfile.mkdtemp()
  readme_md = os.path.join(build_utils.PYTYPE_SRC_ROOT, "README.md")
  temp_readme_md = os.path.join(temp_dir, "README.md")
  with open(readme_md) as readme_md_file:
    readme_lines = readme_md_file.readlines()
  with open(temp_readme_md, "w") as temp_readme_md_file:
    readme_text = "".join(readme_lines[2:])  # We strip the build status line.
    temp_readme_md_file.write(readme_text)

  description_rst = os.path.join(build_utils.PYTYPE_SRC_ROOT, "DESCRIPTION.rst")
  new_description_rst = os.path.join(temp_dir, "DESCRIPTION.rst")
  pandoc_cmd = [
      "pandoc", "--from=markdown", "--to=rst",
      "--output=%s" % new_description_rst,
      temp_readme_md,
  ]
  returncode, stdout = build_utils.run_cmd(pandoc_cmd)
  if returncode != 0:
    sys.exit("Running 'pandoc' failed:\n%s" % stdout)

  with open(description_rst) as description_rst_file:
    contents = set(description_rst_file.readlines())
    with open(new_description_rst) as new_description_rst_file:
      new_contents = set(new_description_rst_file.readlines())
  if contents.symmetric_difference(new_contents):
    sys.exit("ERROR: DESCRIPTION.rst is not up to date.")


def check_if_version_is_ok():
  """Prompt the user to confirm that the version in __version__.py is OK."""
  sys.path.append(build_utils.PYTYPE_SRC_ROOT)
  version_mod = __import__("pytype.__version__", fromlist=["pytype"])
  response = input("Making a release with version %s; Continue? " %
                   getattr(version_mod, "__version__"))
  if response not in ["y", "Y", "yes", "YES"]:
    sys.exit("Aborting release.")


def upload_package(package_path, test=False):
  twine_cmd = ["twine", "upload"]
  if test:
    twine_cmd.extend(["--repository", "testpypi"])
  twine_cmd.append(os.path.join(package_path, "*"))
  print("Uploading: %s" % twine_cmd)
  returncode, stdout = build_utils.run_cmd(twine_cmd)
  if returncode != 0:
    raise ReleaseError("Package upload failed:\n%s" % stdout)


class DistributionPackage(object):
  """Context manager to build the pytype distribution package."""

  def __enter__(self):
    sdist_cmd = ["python", "setup.py", "sdist"]
    print("Creating distribution package: %s\n" % sdist_cmd)
    returncode, stdout = build_utils.run_cmd(sdist_cmd)
    if returncode != 0:
      raise ReleaseError("Running %s failed:\n%s" % (sdist_cmd, stdout))
    # The sdist command creates the distribution package in a directory
    # named "dist"
    self.dist_path = os.path.join(build_utils.PYTYPE_SRC_ROOT, "dist")
    return self.dist_path

  def __exit__(self, exc_type, exc_val, exc_tb):
    print("Deleting the distribution directory ...\n")
    shutil.rmtree(self.dist_path)
    print("Deleting the metadata directory ...\n")
    shutil.rmtree(os.path.join(build_utils.PYTYPE_SRC_ROOT, "pytype.egg-info"))
    return False


def main():
  args = parse_args()

  verify_no_pytype_installation_exists()
  verify_description_rst_is_up_to_date()
  check_if_version_is_ok()
  verify_pypirc_exists()

  try:
    with DistributionPackage() as pkg_path:
      upload_package(pkg_path, args.mode == TEST_MODE)
  except ReleaseError as error:
    sys.exit(">>> Release Failed <<<\n%s" % error.msg)
  print("!!! Release Successfull !!!\n")


if __name__ == "__main__":
  main()
