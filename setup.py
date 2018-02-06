#!/usr/bin/env python

# pylint: disable=bad-indentation

from distutils.core import setup, Extension

import glob
import os


def scan_package_data(path, pattern, check):
    path = os.path.join(*path)
    result = []
    for subdir, _, _ in os.walk(path):
        full_pattern = os.path.join(subdir, pattern)
        if glob.glob(full_pattern):
          # Once we know that it matches files, we store the pattern itself.
          result.append(full_pattern)
    assert os.path.join(path, *check) in result
    return result


def get_builtin_files():
    builtins = scan_package_data(['pytype', 'pytd', 'builtins'], '*.py*',
                                 check=['3', '*.py*'])
    stdlib = scan_package_data(['pytype', 'pytd', 'stdlib'], '*.pytd',
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
)


setup(
    name='pytype',
    version='0.2',
    description='Python type inferencer',
    maintainer='Google',
    maintainer_email='pytypedecl-dev@googlegroups.com',
    url='http://github.com/google/pytype',
    packages=['pytype',
              'pytype/pyc',
              'pytype/pyi',
              'pytype/pytd',
              'pytype/pytd/parse',
              'pytype/typegraph',
             ],
    scripts=['scripts/pytype', 'scripts/pytd'],
    package_data={'pytype': get_builtin_files()},
    requires=['pyyaml (>=3.11)'],
    install_requires=['pyyaml>=3.11'],
    classifiers=['Programming Language :: Python :: 2.7'],
    ext_modules = [parser_ext],
)
