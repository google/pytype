#!/usr/bin/env python

"""Generate cross references from a project."""

from __future__ import print_function

import signal
import sys

from pytype import utils
from pytype.pytd.parse import node

from pytype.tools.xref import debug
from pytype.tools.xref import indexer
from pytype.tools.xref import parse_args
from pytype.tools.xref import output


def main():
  try:
    _, kythe_args, options = parse_args.parse_args(sys.argv[1:])
  except utils.UsageError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)

  node.SetCheckPreconditions(options.check_preconditions)

  if options.timeout is not None:
    signal.alarm(options.timeout)

  ix = indexer.process_file(options, kythe_args=kythe_args)
  if options.debug:
    debug.show_index(ix)
  else:
    output.output_kythe_graph(ix)


if __name__ == "__main__":
  sys.exit(main())
