"""Import and set up the imports_map."""

import collections
import logging
import os

log = logging.getLogger(__name__)


def _read_imports_map(options_info_path):
  """Read the imports_map file, fold duplicate entries into a multimap."""
  if options_info_path is None:
    return None
  imports_multimap = collections.defaultdict(set)
  with open(options_info_path) as fi:
    for line in fi:
      line = line.strip()
      if line:
        short_path, path = line.split(" ", 1)
        short_path, _ = os.path.splitext(short_path)  # drop extension
        imports_multimap[short_path].add(path)
  # Sort the multimap. Move items with '#' in the base name, generated for
  # analysis results via --api, first, so we prefer them over others.
  return {short_path: sorted(paths, key=os.path.basename)
          for short_path, paths in imports_multimap.items()}


def _validate_imports_map(imports_map):
  """Validate the imports map against the command line arguments.

  Args:
    imports_map: The map returned by _read_imports_map.
  Returns:
    A list of invalid entries, in the form (short_path, long_path)
  """
  errors = []
  for short_path, paths in imports_map.items():
    for path in paths:
      if not os.path.exists(path):
        errors.append((short_path, path))
  if errors:
    log.error("Invalid imports_map entries (checking from root dir: %s)",
              os.path.abspath("."))
    for short_path, path in errors:
      log.error("  file does not exist: %r (mapped from %r)", path, short_path)
  return errors


def build_imports_map(options_info_path, output=None):
  """Create a file mapping from a .imports_info file.

  Builds a dict of short_path to full name
     (e.g. "path/to/file.py" =>
           "$GENDIR/rulename~~pytype-gen/path_to_file.py~~pytype"
  Args:
    options_info_path: The file with the info (may be None, for do-nothing)
    output: The output file from the command line. When validating
             imports_info, this output should *not* exist.
  Returns:
    Dict of .py short_path to list of .pytd path or None if no options_info_path
  Raises:
    ValueError if the imports map is invalid
  """
  imports_multimap = _read_imports_map(options_info_path)

  # Output warnings for all multiple
  # mappings and keep the lexicographically first.
  for short_path, paths in imports_multimap.items():
    if len(paths) > 1:
      log.warn("Multiple files for %r => %r ignoring %r",
               short_path, paths[0], paths[1:])
  imports_map = {short_path: os.path.abspath(paths[0])
                 for short_path, paths in imports_multimap.items()}
  # It's not helpful for a file that's being analyzed to import its own pyi,
  # because we're trying to update that information!
  # This _usually_ isn't a problem, but it can be if an __init__.py imports
  # one of its submodules -- the submodule will be read as an Any from the pyi.
  if output:
    for k, v in imports_map.items():
      # Our convention is that if a pyi is generated twice, the first path is
      # the second plus some suffix such as `-1`.
      if output in v:
        del imports_map[k]
        break

  errors = _validate_imports_map(imports_multimap)
  if errors:
    msg = "Invalid imports_map: %s\nBad entries:\n" % options_info_path
    msg += "\n".join("  %s -> %s" % (k, v) for k, v in errors)
    raise ValueError(msg)

  # Add the potential directory nodes for adding "__init__", because some build
  # systems automatically create __init__.py in empty directories. These are
  # added with the path name appended with "/" (os.sep), mapping to the empty
  # file.  See also load_pytd._import_file which also checks for an empty
  # directory and acts as if an empty __init__.py is there.
  dir_paths = {}
  for short_path, path in sorted(imports_map.items()):
    dir_paths[short_path] = path
    short_path_pieces = short_path.split(os.sep)
    # If we have a mapping file foo/bar/quux.py', then the pieces are ["foo",
    # "bar", "quux"] and we want to add foo/__init__.py and foo/bar/__init__.py
    for i in range(1, len(short_path_pieces)):
      intermediate_dir_init = os.path.join(*(
          short_path_pieces[:i] + ["__init__"]))
      if (intermediate_dir_init not in imports_map and
          intermediate_dir_init not in dir_paths):
        log.warn("Created empty __init__ %r", intermediate_dir_init)
        dir_paths[intermediate_dir_init] = os.devnull
  return dir_paths
