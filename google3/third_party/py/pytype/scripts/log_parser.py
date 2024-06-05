"""Parse pytype --debug-logs output."""

import sys


def parse_file(fname):
  """Parse log file and write to stdout."""
  with open(fname) as f:
    lines = f.readlines()
  last_time = 0
  last_func = ""
  for i, line in enumerate(lines):
    if not line.startswith(":"):
      continue
    _, time, level, module, func, lineno, _ = line.split(":", 6)
    del level, lineno  # unused
    if last_func != func:
      time = float(time)
      dtime = time - last_time
      last_time = time
      print(f"{i:5d} {dtime} {module}:{func}")
    last_func = func


if __name__ == "__main__":
  parse_file(sys.argv[1])
