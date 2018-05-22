#!/usr/bin/env python
"""Pytype setup file."""

# pylint: disable=bad-indentation

import glob
import io
import os
import shutil
import sysconfig

from setuptools import setup, Extension  # pylint: disable=g-multiple-import


# Path to directory containing setup.py
here = os.path.abspath(os.path.dirname(__file__))


# Detect the c++ compiler. We need to do this because clang on darwin requires
# some extra flags, but gcc does not support those flags.
config_vars = sysconfig.get_config_vars()
cc = config_vars['CC']
if 'clang' in cc:
  extra_compile_args = ['-std=c++11', '-stdlib=libc++']
  extra_link_args = ['-stdlib=libc++']
else:
  extra_compile_args = ['-std=c++11']
  extra_link_args = []


# Copy checked-in generated files to where they are expected by setup.py.
# This is an interim step until we completely get rid of the generated files.
pyi_dir = os.path.join(here, 'pytype', 'pyi')
gen_dir = os.path.join(pyi_dir, 'gen')
for f in [
    'lexer.lex.cc',
    'location.hh',
    'parser.tab.cc',
    'parser.tab.hh',
    'position.hh',
    'stack.hh'
]:
  shutil.copy(os.path.join(gen_dir, f), os.path.join(pyi_dir, f))


# Copy typeshed to pytype/typeshed if the symlink doesn't work
# (workaround for installing on windows).
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
                             check=['3', 'asyncio', '*.pytd'])
  typeshed = scan_package_data(['typeshed'], '*.pyi',
                               check=['stdlib', '2', '*.pyi'])
  return builtins + stdlib + typeshed


parser_ext = Extension(
    'pytype.pyi.parser_ext',
    sources=[
        'pytype/pyi/parser_ext.cc',
        'pytype/pyi/lexer.lex.cc',
        'pytype/pyi/parser.tab.cc',
    ],
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args
)


# Read the long-description from a file.
with io.open(os.path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
  long_description = '\n' + f.read()


# Load the package's __version__.py module as a dictionary.
about = {}
with open(os.path.join(here, 'pytype', '__version__.py')) as f:
  exec (f.read(), about)  # pylint: disable=exec-used


setup(
    name='pytype',
    version=about['__version__'],
    description='Python type inferencer',
    long_description=long_description,
    maintainer='Google',
    maintainer_email='pytypedecl-dev@googlegroups.com',
    url='http://github.com/google/pytype',
    packages=[
        'pytype',
        'pytype/pyc',
        'pytype/pyi',
        'pytype/pytd',
        'pytype/pytd/parse',
        'pytype/tools',
        'pytype/tools/analyze_project',
        'pytype/typegraph',
    ],
    scripts=[
        'scripts/pytype',
        'scripts/pytd',
        'scripts/pytype-all',
    ],
    package_data={'pytype': get_builtin_files()},
    install_requires=[
        'importlab',
        'pyyaml (>=3.11)',
        'six'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development',
    ],
    ext_modules=[parser_ext],
)
