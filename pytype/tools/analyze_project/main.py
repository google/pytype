#!/usr/bin/env python

# Copyright 2017 Google Inc.
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

"""Analyze an entire project using pytype."""

from __future__ import print_function

import logging
import sys
import tempfile

import importlab.environment
import importlab.fs
import importlab.graph
import importlab.output

from pytype import io
from pytype.tools import environment
from pytype.tools import tool_utils
from pytype.tools.analyze_project import config
from pytype.tools.analyze_project import environment as analyze_project_env
from pytype.tools.analyze_project import parse_args
from pytype.tools.analyze_project import pytype_runner


def main():
  parser = parse_args.make_parser()
  args = parser.parse_args(sys.argv[1:])

  if args.version:
    print(io.get_pytype_version())
    sys.exit(0)

  tool_utils.setup_logging_or_die(args.verbosity)

  if args.generate_config:
    config.generate_sample_config_or_die(args.generate_config,
                                         parser.pytype_single_args)
    sys.exit(0)

  conf = parser.config_from_defaults()
  # File options overwrite defaults.
  file_config = config.read_config_file_or_die(args.config)
  parser.postprocess(file_config, from_strings=True)
  conf.populate_from(file_config)
  # Command line arguments overwrite file options.
  conf.populate_from(args)
  conf.inputs -= conf.exclude
  if args.no_cache:
    conf.output = tempfile.mkdtemp()
  if not conf.pythonpath:
    conf.pythonpath = environment.compute_pythonpath(conf.inputs)
  logging.info('\n  '.join(['Configuration:'] + str(conf).split('\n')))

  if not conf.inputs:
    parser.parser.error('Need an input.')

  # Importlab needs the python exe, so we check it as early as possible.
  environment.check_python_exe_or_die(conf.python_version)

  typeshed = environment.initialize_typeshed_or_die()
  env = analyze_project_env.create_importlab_environment(conf, typeshed)
  print('Computing dependencies')
  import_graph = importlab.graph.ImportGraph.create(env, conf.inputs, trim=True)

  if args.tree:
    print('Source tree:')
    importlab.output.print_tree(import_graph)
    sys.exit(0)

  if args.unresolved:
    print('Unresolved dependencies:')
    for imp in sorted(import_graph.get_all_unresolved()):
      print(' ', imp.name)
    sys.exit(0)

  # Main usage mode: analyze the project file by file in dependency order.

  logging.info('Source tree:\n%s',
               importlab.output.formatted_deps_list(import_graph))
  tool_utils.makedirs_or_die(conf.output, 'Could not create output directory')
  deps = pytype_runner.deps_from_import_graph(import_graph)
  runner = pytype_runner.PytypeRunner(conf, deps)
  return runner.run()


if __name__ == '__main__':
  sys.exit(main())
