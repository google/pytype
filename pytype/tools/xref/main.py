#!/usr/bin/env python

"""Generate cross references from a project."""

from __future__ import print_function

import signal
import sys

from pytype import config
from pytype import utils
from pytype.pytd.parse import node

from pytype.tools.xref import indexer
from pytype.tools.xref import output


def main():
  try:
    options = config.Options(sys.argv[1:])
  except utils.UsageError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)

  node.SetCheckPreconditions(options.check_preconditions)

  if options.timeout is not None:
    signal.alarm(options.timeout)

  v = indexer.process_file(options)
  output.output_kythe_graph(v)


if __name__ == "__main__":
  sys.exit(main())
