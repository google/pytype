"""Import and set up the imports_map."""


# The imports_map is special for some build systems, such as Bazel.  Each entry
# consists of a short name and a full name; this allows handling build targets
# in a uniform way, with freedom to put the actual file in a different place
# (e.g., if the source tree is read-only and there are generated source files
# that must reside elsewhere).

# Each invocation of pytype is given an imports_info file by the build
# system. The complete mapping of imports name to actual file can be generated
# by recursively starting with the current invocations.


# The keys are the module paths *without* the trailing .py
# TODO(pludemann): revisit this decision and reinstate the .py, because: (a)
#                  that's the only thing that should appear (.pytd inputs are
#                  handled outside of pytype); (b) the src_out_pairs_py data
#                  already has .py for src; and (c) it removes one hard-coding
#                  of ".py".

# It is possible to have a 1:many mapping from a short name to multiple full
# names (e.g., if two separate build actions process the same file, but output
# to different places). For handling this, we depend on the build system
# employing a convention to create full names that sort first.



import collections
import logging
import os
import shlex
import textwrap

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
        short_path, path = shlex.split(line)
        short_path, _ = os.path.splitext(short_path)  # drop extension
        imports_multimap[short_path].add(path)
  # Sort the multimap. Move items with '#' in the base name, generated for
  # analysis results via --api, first, so we prefer them over others.
  return {short_path: sorted(paths, key=os.path.basename)
          for short_path, paths in imports_multimap.items()}


def _validate_map(imports_map, src_out):
  """Validate the imports map against the command line arguments.

  Validate the map. Note that main.py has ensured that all output files also
  exist, in case they're actually used for input, e.g. when there are multiple
  files being processed.

  Args:
    imports_map: The map returned by _read_imports_map.
    src_out: The command line arguments - pairs of file, as specified on the
      command line as "src:out".
  Raises:
    AssertionError: If we found an error in the imports map.
  """
  # If pytype is processing multiple files that import each other, during the
  # first pass, we don't have a .pyi for them yet, even though they might be
  # mentioned in the imports_map. So fill them with temporary contents.
  for input, output in src_out:
    if os.path.exists(output):
      log.error("output file %r (from processing %r) already exists; "
                "will be overwritten",
                os.path.realpath(output), input)
    with open(output, "w") as fi:
      fi.write(textwrap.dedent("""\
          # If you see this comment, it means pytype hasn't properly
          # processed %r to %r.
          def __getattr(name) -> Any: ...
      """ % (input, output)))

  # Now, validate the imports_map.
  # TODO(pludemann): the tests depend on os.path.realpath being canonical
  #                  and for os.path.samefile(path1, path2) being equivalent
  #                  to os.path.realpath(path1) == os.path.realpath(path2)
  for short_path, paths in imports_map.items():
    for path in paths:
      if not os.path.exists(path):
        log.error("imports_map file does not exist: %r (mapped from %r)",
                  path, short_path)
        log.error("tree walk of files from '.' (%r):", os.path.abspath("."))
        for dirpath, _, files in os.walk(".", followlinks=False):
          logging.error("... dir %r: %r", dirpath, files)
        log.error("end tree walk of files from '.'")
        raise AssertionError("bad import map")


def build_imports_map(options_info_path, src_out=None):
  """Create a file mapping from a .imports_info file.

  Builds a dict of short_path to full name
     (e.g. "path/to/file.py" =>
           "$GENDIR/rulename~~pytype-gen/path_to_file.py~~pytype"
  Args:
    options_info_path: The file with the info (may be None, for do-nothing)
    src_out: The src/output files from the command line. When validating the
             imports_info, these outputs should *not* exist. (The check is only
             done if options_Info_path is not None, because other build systems
             might not ensure that output files are deleted before processing).
  Returns:
    Dict of .py short_path to list of .pytd path or None if no options_info_path
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

  if src_out is not None:
    _validate_map(imports_multimap, src_out)

  # Add the potential directory nodes for adding "__init__", because some build
  # systems automatically create __init__.py in empty directories. These are
  # added with the path name appended with "/" (os.sep), mapping to the empty
  # file.  See also load_pytd._import_file which also checks for an empty
  # directory and acts as if an empty __init__.py is there.
  # TODO(pludemann): remove either this code or the code in pytd_load.
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
