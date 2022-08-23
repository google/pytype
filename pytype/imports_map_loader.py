"""Import and set up the imports_map."""

import collections
import logging
import os

from typing import Dict, List, Optional, Tuple

from pytype.platform_utils import path_utils

log = logging.getLogger(__name__)


# Type aliases.
MultimapType = Dict[str, List[str]]
ItemType = Tuple[str, str]
ImportsMapType = Dict[str, str]


class ImportsMapBuilder:
  """Build an imports map from (short_path, path) pairs."""

  def __init__(self, options):
    self.options = options

  def _read_from_file(self, path) -> List[ItemType]:
    """Read the imports_map file."""
    items = []
    with self.options.open_function(path) as f:
      for line in f:
        line = line.strip()
        if line:
          short_path, path = line.split(" ", 1)
          items.append((short_path, path))
    return items

  def _build_multimap(self, items: List[ItemType]) -> MultimapType:
    """Build a multimap from a list of (short_path, path) pairs."""
    # TODO(mdemello): Keys should ideally be modules, not short paths.
    imports_multimap = collections.defaultdict(set)
    for short_path, path in items:
      short_path, _ = path_utils.splitext(short_path)  # drop extension
      imports_multimap[short_path].add(path)
    # Sort the multimap. Move items with '#' in the base name, generated for
    # analysis results via --api, first, so we prefer them over others.
    return {
        short_path: sorted(paths, key=path_utils.basename)
        for short_path, paths in imports_multimap.items()
    }

  def _validate(self, imports_map: MultimapType) -> List[ItemType]:
    """Validate the imports map against the command line arguments.

    Args:
      imports_map: The map returned by _read_imports_map.
    Returns:
      A list of invalid entries, in the form (short_path, long_path)
    """
    errors = []
    for short_path, paths in imports_map.items():
      for path in paths:
        if not path_utils.exists(path):
          errors.append((short_path, path))
    if errors:
      log.error("Invalid imports_map entries (checking from root dir: %s)",
                path_utils.abspath("."))
      for short_path, path in errors:
        log.error("  file does not exist: %r (mapped from %r)",
                  path, short_path)
    return errors

  def _finalize(
      self, imports_multimap: MultimapType, path: str = ""
  ) -> ImportsMapType:
    """Generate the final imports map."""
    # Output warnings for all multiple mappings and keep the lexicographically
    # first path for each.
    for short_path, paths in imports_multimap.items():
      if len(paths) > 1:
        log.warning("Multiple files for %r => %r ignoring %r",
                    short_path, paths[0], paths[1:])
    imports_map = {
        short_path: path_utils.abspath(paths[0])
        for short_path, paths in imports_multimap.items()
    }

    errors = self._validate(imports_multimap)
    if errors:
      msg = f"Invalid imports_map: {path}\nBad entries:\n"
      msg += "\n".join(f"  {k} -> {v}" for k, v in errors)
      raise ValueError(msg)

    # Add the potential directory nodes for adding "__init__", because some
    # build systems automatically create __init__.py in empty directories. These
    # are added with the path name appended with "/", mapping to the empty file.
    # See also load_pytd._import_file which also checks for an empty directory
    # and acts as if an empty __init__.py is there.
    dir_paths = {}
    for short_path, full_path in sorted(imports_map.items()):
      dir_paths[short_path] = full_path
      short_path_pieces = short_path.split(path_utils.sep)
      # If we have a mapping file foo/bar/quux.py', then the pieces are
      # ["foo", "bar", "quux"] and we want to add foo/__init__.py and
      # foo/bar/__init__.py
      for i in range(1, len(short_path_pieces)):
        intermediate_dir_init = path_utils.join(*(short_path_pieces[:i] +
                                                  ["__init__"]))
        if (intermediate_dir_init not in imports_map and
            intermediate_dir_init not in dir_paths):
          log.warning("Created empty __init__ %r", intermediate_dir_init)
          dir_paths[intermediate_dir_init] = os.devnull
    return dir_paths

  def build_from_file(
      self, path: Optional[str]
  ) -> Optional[ImportsMapType]:
    """Create an ImportsMap from a .imports_info file.

    Builds a dict of short_path to full name
       (e.g. "path/to/file.py" =>
             "$GENDIR/rulename~~pytype-gen/path_to_file.py~~pytype"
    Args:
      path: The file with the info (may be None, for do-nothing)
    Returns:
      Dict of .py short_path to list of .pytd path or None if no path
    Raises:
      ValueError if the imports map is invalid
    """
    if not path:
      return None
    items = self._read_from_file(path)
    return self.build_from_items(items, path)

  def build_from_items(
      self, items: Optional[List[ItemType]], path=None
  ) -> Optional[ImportsMapType]:
    """Create a file mapping from a list of (short path, path) tuples.

    Builds a dict of short_path to full name
       (e.g. "path/to/file.py" =>
             "$GENDIR/rulename~~pytype-gen/path_to_file.py~~pytype"
    Args:
      items: A list of (short_path, full_path) tuples.
      path: The file from which the items were read (for error messages)
    Returns:
      Dict of .py short_path to list of .pytd path or None if no items
    Raises:
      ValueError if the imports map is invalid
    """
    if not items:
      return None
    imports_multimap = self._build_multimap(items)
    assert imports_multimap is not None
    return self._finalize(imports_multimap, path)
