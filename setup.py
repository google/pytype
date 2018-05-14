#!/usr/bin/env python

# pylint: disable=bad-indentation

from setuptools import setup, Extension  # pylint: disable=multiple-import

import glob
import io
import os


def scan_package_data(path, pattern, check):
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
    sources = [
        'pytype/pyi/parser_ext.cc',
        'pytype/pyi/lexer.lex.cc',
        'pytype/pyi/parser.tab.cc',
        ],
    extra_compile_args=['-std=c++11']
)


here = os.path.abspath(os.path.dirname(__file__))


# Read the long-description from a file.
with io.open(os.path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = '\n' + f.read()


# Load the package's __version__.py module as a dictionary.
about = {}
with open(os.path.join(here, 'pytype', '__version__.py')) as f:
    exec(f.read(), about)  # pylint: disable=exec-used


setup(
    name='pytype',
    version=about['__version__'],
    description='Python type inferencer',
    long_description=long_description,
    maintainer='Google',
    maintainer_email='pytypedecl-dev@googlegroups.com',
    url='http://github.com/google/pytype',
    packages=['pytype',
              'pytype/pyc',
              'pytype/pyi',
              'pytype/pytd',
              'pytype/pytd/parse',
              'pytype/tools',
              'pytype/tools/analyze_project',
              'pytype/typegraph',
             ],
    scripts=['scripts/pytype',
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
    ext_modules = [parser_ext],
)
