#!/usr/bin/env python
"""Pytype setup file."""

# pylint: disable=bad-indentation

import glob
import os
import re
import shutil
import sys

from setuptools import setup

# Path to directory containing setup.py
here = os.path.abspath(os.path.dirname(__file__))

# Get the pybind11 setup helpers
#
# This is appended, so if already available in site-packages, that is used
# instead
sys.path.append(os.path.join(here, "pybind11"))

from pybind11.setup_helpers import Pybind11Extension  # pylint: disable=g-import-not-at-top,wrong-import-position


def get_typegraph_ext():
  """Generates the typegraph extension."""
  return Pybind11Extension(
      'pytype.typegraph.cfg',
      sources=[
          "pytype/typegraph/cfg.cc",
          "pytype/typegraph/cfg_logging.cc",
          "pytype/typegraph/pylogging.cc",
          "pytype/typegraph/reachable.cc",
          "pytype/typegraph/solver.cc",
          "pytype/typegraph/typegraph.cc",
      ],
      depends=[
          "pytype/typegraph/cfg_logging.h",
          "pytype/typegraph/map_util.h",
          "pytype/typegraph/memory_util.h",
          "pytype/typegraph/pylogging.h",
          "pytype/typegraph/reachable.h",
          "pytype/typegraph/solver.h",
          "pytype/typegraph/typegraph.h",
      ],
      cxx_std=11,
  )

def copy_typeshed():
  """Windows install workaround: copy typeshed if the symlink doesn't work."""
  internal_typeshed = os.path.join(here, 'pytype', 'typeshed')
  if not os.path.exists(os.path.join(internal_typeshed, 'stdlib')):
    if os.path.exists(internal_typeshed):
      # If it is a symlink, remove it
      try:
        os.remove(internal_typeshed)
      except OSError:
        # This might be a directory that has not got a complete typeshed
        # installation in it; delete and copy it over again.
        shutil.rmtree(internal_typeshed)
    shutil.copytree(os.path.join(here, 'typeshed'), internal_typeshed)


def scan_package_data(path, pattern, check):
  """Scan for files to be included in package_data."""

  # We start off in the setup.py directory, but package_data is relative to
  # the pytype/ directory.
  package_dir = 'pytype'
  path = os.path.join(*path)
  full_path = os.path.join(package_dir, path)
  result = []
  for subdir, _, _ in os.walk(full_path):
    full_pattern = os.path.join(subdir, pattern)
    if glob.glob(full_pattern):
      # Once we know that it matches files, we store the pattern itself,
      # stripping off the prepended pytype/
      result.append(os.path.relpath(full_pattern, package_dir))
  assert os.path.join(path, *check) in result
  return result


def get_data_files():
  builtins = scan_package_data(['stubs', 'builtins'], '*.pytd',
                               check=['attr', '*.pytd'])
  stdlib = scan_package_data(['stubs', 'stdlib'], '*.pytd',
                             check=['*.pytd'])
  typeshed = (scan_package_data(['typeshed'], '*.pyi',
                                check=['stdlib', '*.pyi']) +
              ['typeshed/stdlib/VERSIONS'] +
              scan_package_data(['typeshed'], 'METADATA.toml',
                                check=['stubs', 'six', 'METADATA.toml']))
  merge_pyi_grammar = ['tools/merge_pyi/Grammar.txt']
  return builtins + stdlib + typeshed + merge_pyi_grammar


def get_long_description():
  # Read the long-description from a file.
  with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    desc = '\n' + f.read()
  # Fix relative links to the pytype docs.
  return re.sub(
      r'\[(.+)\]: docs/',
      r'[\g<1>]: https://github.com/google/pytype/blob/main/docs/', desc)


copy_typeshed()

# Only options configured at build time are declared here, everything else is
# declared in setup.cfg
setup(
    long_description=get_long_description(),
    package_data={'pytype': get_data_files()},
    ext_modules=[get_typegraph_ext()],
)
