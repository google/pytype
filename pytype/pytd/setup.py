#!/usr/bin/python

# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Distutils-based script to build and install pytypedecl.

Run
  python setup.py build
to build and
  python setup.py install
to install.
"""

from distutils.core import setup

setup(name='pytypedecl',
      version='0.1',
      description='Runtime type checking',
      url='http://www.github.com/google/pytypedecl',
      requires=['ply(>=3.0)'],
      package_dir={'pytypedecl': ''},
      packages=['pytypedecl', 'pytypedecl.parse'],
     )
