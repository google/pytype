#!/usr/bin/env python
"""Pytype setup file."""

# pylint: disable=bad-indentation

import glob
import io
import os
import re
import shutil
import sys

from setuptools import setup, Extension

# Path to directory containing setup.py
here = os.path.abspath(os.path.dirname(__file__))

# Get the pybind11 setup helpers
#
# This is appended, so if already available in site-packages, that is used
# instead
sys.path.append(os.path.join(here, "pybind11"))

from pybind11.setup_helpers import Pybind11Extension  # pylint: disable=g-import-not-at-top,wrong-import-position

try:
  # The repository root is not on the pythonpath with PEP 517 builds
  if 'build_scripts' in os.listdir(here):
      sys.path.append(here)

  from build_scripts import build_utils  # pylint: disable=g-import-not-at-top
except ImportError:
  # When build_utils is present, we'll generate parser files for installing
  # from source or packaging into a PyPI release.
  build_utils = None


def get_parser_ext():
  """Get the parser extension."""
  # We need some platform-dependent compile args for the C extensions.
  if sys.platform == 'win32':
    # windows does not have unistd.h; lex/yacc needs this define.
    extra_compile_args = ['-DYY_NO_UNISTD_H']
    extra_link_args = []
  elif sys.platform == 'darwin':
    # clang on darwin requires some extra flags, which gcc does not support
    extra_compile_args = ['-std=c++11', '-stdlib=libc++']
    extra_link_args = ['-stdlib=libc++']
  else:
    extra_compile_args = ['-std=c++11']
    extra_link_args = []
  return Extension(
      'pytype.pyi.parser_ext',
      sources=[
          'pytype/pyi/parser_ext.cc',
          'pytype/pyi/lexer.lex.cc',
          'pytype/pyi/parser.tab.cc',
      ],
      extra_compile_args=extra_compile_args,
      extra_link_args=extra_link_args,
  )


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
  builtins = scan_package_data(['pytd', 'builtins'], '*.py*',
                               check=['3', '*.py*'])
  stdlib = scan_package_data(['pytd', 'stdlib'], '*.pytd',
                             check=['3', '*.pytd'])
  typeshed = scan_package_data(['typeshed'], '*.pyi',
                               check=['stdlib', '2', '*.pyi'])
  merge_pyi_grammar = ['tools/merge_pyi/Grammar.txt']
  return builtins + stdlib + typeshed + merge_pyi_grammar


def get_long_description():
  # Read the long-description from a file.
  with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    desc = '\n' + f.read()
  # Fix relative links to the pytype docs.
  return re.sub(
      r'\[(.+)\]: docs/',
      r'[\g<1>]: https://github.com/google/pytype/blob/master/docs/', desc)


copy_typeshed()
if build_utils:
  e = build_utils.generate_files()
  assert not e, e

# Only options configured at build time are declared here, everything else is
# declared in setup.cfg
setup(
    long_description=get_long_description(),
    package_data={'pytype': get_data_files()},
    ext_modules=[get_parser_ext(), get_typegraph_ext()],
)

if build_utils:
  build_utils.clean_generated_files()
