#!/usr/bin/env python

from distutils.core import setup

setup(
    name='pytype',
    version='0.2',
    description='Python type inferencer',
    maintainer='Google',
    maintainer_email='pytypedecl-dev@googlegroups.com',
    url='http://github.com/google/pytype',
    packages=['pytype', 'pytype/pyc', 'pytype/pytd', 'pytype/pytd/parse'],
    scripts=['scripts/pytype', 'scripts/pytd'],
    package_data={'pytype': ['pytd/builtins/*']},
)
