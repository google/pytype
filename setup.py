#!/usr/bin/env python

# pylint: disable=bad-indentation

from distutils.core import setup

import glob
import os


def scan_package_data(path, pattern):
    result = []
    for subdir, _, _ in os.walk(path):
        full_pattern = os.path.join(subdir, pattern)
        if glob.glob(full_pattern):
          # Once we know that it matches files, we store the pattern itself.
          result.append(full_pattern)
    return result


typeshed = scan_package_data('typeshed', '*.pyi')
assert 'typeshed/stdlib/2.7/*.pyi' in typeshed


setup(
    name='pytype',
    version='0.2',
    description='Python type inferencer',
    maintainer='Google',
    maintainer_email='pytypedecl-dev@googlegroups.com',
    url='http://github.com/google/pytype',
    packages=['pytype',
              'pytype/pyc',
              'pytype/pytd',
              'pytype/pytd/parse',
             ],
    scripts=['scripts/pytype', 'scripts/pytd'],
    package_data={'pytype': ['pytd/builtins/*.pytd',
                             'pytd/stdlib/*.pytd',
                             'pytd/stdlib/*/*.pytd',
                            ] + typeshed},
    requires=['ply (>=3.4)', 'pyyaml (>=3.11)'],
    install_requires=['ply>=3.4', 'pyyaml>=3.11'],
    classifier=["Programming Language :: Python :: 2.7"],
)
