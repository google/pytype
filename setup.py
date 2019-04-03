#!/usr/bin/env python
"""Pytype setup file."""

# pylint: disable=bad-indentation

import glob
import io
import os
import shutil
import sys

from setuptools import setup, Extension  # pylint: disable=g-multiple-import

try:
  from build_scripts import build_utils  # pylint: disable=g-import-not-at-top
except ImportError:
  # When build_utils is present, we'll generate parser files for installing
  # from source or packaging into a PyPI release.
  build_utils = None


# Path to directory containing setup.py
here = os.path.abspath(os.path.dirname(__file__))


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
      extra_link_args=extra_link_args
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


def get_builtin_files():
  builtins = scan_package_data(['pytd', 'builtins'], '*.py*',
                               check=['3', '*.py*'])
  stdlib = scan_package_data(['pytd', 'stdlib'], '*.pytd',
                             check=['3', '*.pytd'])
  typeshed = scan_package_data(['typeshed'], '*.pyi',
                               check=['stdlib', '2', '*.pyi'])
  return builtins + stdlib + typeshed


def get_long_description():
  # Read the long-description from a file.
  with io.open(os.path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    return '\n' + f.read()


def get_version():
  # Load the package's __version__.py module as a dictionary.
  about = {}
  with open(os.path.join(here, 'pytype', '__version__.py')) as f:
    exec (f.read(), about)  # pylint: disable=exec-used
  return about['__version__']


def get_install_requires():
  requires = [
      'importlab (>=0.5)',
      'ninja',
      'pyyaml (>=3.11)',
      'six',
  ]
  if sys.version_info >= (3, 3):
    requires.append('typed_ast')
  return requires


copy_typeshed()
if build_utils:
  e = build_utils.generate_files()
  assert not e, e
setup(
    name='pytype',
    version=get_version(),
    description='Python type inferencer',
    long_description=get_long_description(),
    maintainer='Google',
    maintainer_email='pytype@googlegroups.com',
    url='https://google.github.io/pytype',
    packages=[
        'pytype',
        'pytype/pyc',
        'pytype/pyi',
        'pytype/pytd',
        'pytype/pytd/parse',
        'pytype/tools',
        'pytype/tools/analyze_project',
        'pytype/tools/merge_pyi',
        'pytype/tools/xref',
        'pytype/typegraph',
    ],
    entry_points={
        'console_scripts': [
            'merge-pyi = pytype.tools.merge_pyi.main:main',
            'pytype-single = pytype.main:main',
            'pytd = pytype.pytd.main:main',
            'pytype = pytype.tools.analyze_project.main:main',
            'pyxref = pytype.tools.xref.main:main',
        ]
    },
    package_data={'pytype': get_builtin_files()},
    install_requires=get_install_requires(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development',
    ],
    ext_modules=[get_parser_ext()],
)
if build_utils:
  build_utils.clean_generated_files()
