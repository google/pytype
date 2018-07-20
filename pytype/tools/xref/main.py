#!/usr/bin/env python

# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generate cross references from a project."""

from __future__ import print_function

import collections
import logging
import signal
import sys

from pytype import analyze
from pytype import config
from pytype import errors
from pytype import io
from pytype import load_pytd
from pytype import utils
from pytype.pytd.parse import node


def display_traces(src, opcode_traces):
  """Format and print trace data."""

  out = collections.defaultdict(list)
  for op, symbol, data in opcode_traces:
    out[op.line].append((op.name, symbol, data))
  source = src.split('\n')
  for line in sorted(out.keys()):
    print('%d %s' % (line, source[line - 1]))
    for name, symbol, data in out[line]:
      print('  %s : %s <- %s %s' % (
          name, symbol, data, [type(x) for x in data]))
    print('-------------------')


def process_file(options):
  """Process a single file and return cross references."""

  errorlog = errors.ErrorLog()
  loader = load_pytd.create_loader(options)
  src = io.read_source_file(options.input)
  vm = analyze.CallTracer(
      errorlog=errorlog,
      options=options,
      generate_unknowns=options.protocols,
      store_all_calls=False,
      loader=loader)
  try:
    analyze.infer_types(
        src=src,
        filename=options.input,
        errorlog=errorlog,
        options=options,
        loader=loader,
        tracer_vm=vm)
  except utils.UsageError as e:
    logging.error('Usage error: %s\n', utils.message(e))
    return 1

  display_traces(src, vm.opcode_traces)


def main():
  try:
    options = config.Options(sys.argv[1:])
  except utils.UsageError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)

  node.SetCheckPreconditions(options.check_preconditions)

  if options.timeout is not None:
    signal.alarm(options.timeout)

  return process_file(options)


if __name__ == '__main__':
  sys.exit(main())
