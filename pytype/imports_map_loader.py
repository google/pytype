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

log = logging.getLogger(__name__)


# ModulePathAndPyiPath normally has the short and full path for the same file,
# but sometimes it has two different files (e.g., for a src-out pair).
class ModulePathAndPyiPath(collections.namedtuple(
    "ModulePathAndPyiPath", [
        "short_path",  # The short path as used in the build system
        "path"         # The full path to the actual file
        ])):
  __slots__ = ()

  def __repr__(self):
    prefix, common, suffix = self.path.rpartition(self.short_path)
    if not prefix and not suffix:
      return "[%r]" % common
    elif not prefix and not common:  # short path isn't in path
      return "[%r -> %r]" % (self.short_path, self.path)
    else:
      return "[%r + %r + %r]" % (prefix, common, suffix)


def build_imports_map(options_info_path, src_out):
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
  pytype_provider_deps_files = _read_pytype_provider_deps_files(
      options_info_path)
  # build up a dict of short_path -> list of paths
  imports_multimap = collections.defaultdict(set)
  for short_path, path in pytype_provider_deps_files:
    path_key, path_ext = os.path.splitext(short_path)
    # TODO(pludemann): parameterize this check:
    assert path_ext in (".py", ".pytd"), (path_key, path_ext, short_path)
    imports_multimap[path_key].add(path)

  # Sort the paths (that is, the values in the multimap), so that "#" items are
  # first (using os.path.basename, because that's where the "#" is
  # prepended). This is for situations with multiple versions of the annotations
  # file; we follow the convention that files generated with the --api option
  # have "#", so that they sort first.  Output warnings for all multiple
  # mappings and keep the lexicographically first.
  imports_multimap = {short_path: sorted(paths, key=os.path.basename)
                      for short_path, paths in imports_multimap.items()}
  for short_path, paths in imports_multimap.items():
    if len(paths) > 1:
      log.warn("Multiple files for %r => %r ignoring %r",
               short_path, paths[0], paths[1:])
  # The realpath is only needed for the sanity checks below
  imports_map = {short_path: os.path.realpath(paths[0])
                 for short_path, paths in imports_multimap.items()}

  # Validate the map. Note that main.py has ensured that all output files also
  # exist, in case they're actually used for input, e.g. when there are multiple
  # files being processed.
  # TODO(pludemann): the tests depend on os.path.realpath being canonical
  #                  and for os.path.samefile(path1, path2) being equivalent
  #                  to os.path.realpath(path1) == os.path.realpath(path2)
  cmd_line_outputs = {os.path.realpath(output_filename): input_filename
                      for input_filename, output_filename in src_out}
  for path in cmd_line_outputs:
    if os.path.exists(path):
      log.error("output file %r (from processing %r) already exists; "
                "will be overwritten",
                path, cmd_line_outputs[path])
  for short_path, path in imports_map.items():
    if not os.path.exists(path) and path not in cmd_line_outputs:
      log.error("imports_map file does not exist: %r (mapped from %r)",
                path, short_path)
      log.error("tree walk of files from '.' (%r):", os.path.abspath("."))
      for dirpath, _, files in os.walk(".", followlinks=False):
        logging.error("... dir %r: %r", dirpath, files)
      log.error("end tree walk of files from '.'")
      raise

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


def _read_pytype_provider_deps_files(options_info_path):
  """Read file options_info_path, producing pytype_provider_deps_files."""
  if options_info_path is None:
    return None
  with open(options_info_path) as fi:
    return {ModulePathAndPyiPath(*shlex.split(line.strip()))
            for line in fi if line.strip()}
