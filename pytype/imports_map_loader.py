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
#                  handled outside of pytype; (b) the src_out_pairs_py data
#                  already has .py for src; and (c) it removes one hard-coding
#                  of ".py".

# It is possible to have a 1:many mapping from a short name to multiple full
# names (e.g., if two separate build actions process the same file, but output
# to different places). For handling this, we depend on the build system
# employing a convention to create full names that sort first.



import collections
import itertools
import logging
import operator
import os
import shlex

log = logging.getLogger(__name__)


# FilePaths normally has the short and full path for the same file, but
# sometimes it has two different files (e.g., for a src-out pair).
class FilePaths(collections.namedtuple(
    "FilePaths", [
        "short_path",  # The short path as used in the build system
        "path"         # The full path to the actual file
        ])):
  __slots__ = ()

  def __repr__(self):
    prefix, common, suffix = self.path.rpartition(self.short_path)
    if not prefix and not suffix:
      return "FilePaths(%r)" % common
    if not prefix and not common:  # short path isn't in path
      return super(FilePaths, self).__repr__()
    return "FilePaths(%r + %r + %r)" % (prefix, common, suffix)


# Unless otherwise stated, the fields are set(FilePath).
# The short_path and path components of the FilePath might refer
# to different files (e.g., in src_out)
ImportsInfo = collections.namedtuple(
    "ImportsInfo", [
        "label",                    # rule label (string)
        "src_out_pairs_py",         # Args to pytype: short .py, long .pytd
        "src_out_pairs_pytd",       # short .pytd, long .pytd
        "srcs_filter_py",           # files.srcs, .py only
        "srcs_filter_pytd",          # files.srcs, .pytd only
        "pytype_provider_deps_files",   # transitive src_out_pairs_py
        "transitive_inputs",        # transitive pytd (short_path, path)
        "py_transitive_srcs",       # transitive .py.transitive_sources
        "py_deps",                  # {dependency: list(FilePath)}
        "pytype_deps",              # {dependency: list(FilePath)}
        "py_deps_files",            # list(FilePath) for all py_* dependencies
        "pytype_deps_files",        # list(FilePath) for all pytype dependencies
        ])


def build_imports_map(options_info_path, empty_init_path, src_out):
  """Create a file mapping from a .imports_info file.

  Builds a dict of short_path to full name
     (e.g. "path/to/file.py" =>
           "$GENDIR/rulename~~pytype-gen/path_to_file.py~~pytype"
  Args:
    options_info_path: The file with the info (may be None, for do-nothing)
    empty_init_path: If given, is the path to an empty file (for auto-generated
                     __init__.py files, which applies only to processing under
                     some build systems.
    src_out: The src/output files from the command line. When validating the
             imports_info, these outputs should *not* exist. (The check is only
             done if options_Info_path is not None, because other build systems
             might not ensure that output files are deleted before processing).
  Returns:
    Dict of .py short_path to list of .pytd path or None if no options_info_path

  """
  imports_info = _read_imports_info(options_info_path)
  # build up a dict of short_path -> list of paths
  imports_multimap = collections.defaultdict(list)
  for short_path, path in imports_info.pytype_provider_deps_files:
    path_key, path_ext = os.path.splitext(short_path)
    # TODO(pludemann): parameterize this check:
    assert path_ext in (".py", ".pytd"), (path_key, path_ext, short_path)
    imports_multimap[path_key].append(path)


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

  return imports_map


def _read_imports_info(options_info_path):
  """Read file options_info_path, producing ImportsInfo."""
  if options_info_path is None:
    return  None
  # Read the imports map file and turn it into a dict(key: list-of-items).
  # For each line:
  #   Process using shlex.split, which gives a list of tokens.
  # Throw away empty lines and sort the list.
  # Group by the first token in each line(list of tokens)
  # Transform into a dict, mapping to list of FilePaths.
  imports_dict = collections.defaultdict(
      list,
      {k: [x[1:] for x in gr] for k, gr in itertools.groupby(
          sorted(filter(None, map(shlex.split, open(options_info_path)))),
          operator.itemgetter(0))})

  # TODO(pludemann): Delete all that aren't used here.
  label, = imports_dict["label"]
  label, = label  # label = imports_dict["label"][0][0] with verification
  imports_info = ImportsInfo(
      label=label,
      src_out_pairs_py=frozenset(
          FilePaths(*f) for f in imports_dict["src_out_pairs_py"]),
      src_out_pairs_pytd=frozenset(
          FilePaths(*f) for f in imports_dict["src_out_pairs_pytd"]),
      srcs_filter_py=frozenset(
          FilePaths(*f) for f in imports_dict["srcs_filter_py"]),
      srcs_filter_pytd=frozenset(
          FilePaths(*f) for f in imports_dict["srcs_filter_pytd"]),
      pytype_provider_deps_files=frozenset(
          FilePaths(*f) for f in imports_dict["pytype_provider_deps_files"]),
      py_transitive_srcs=frozenset(
          FilePaths(*f) for f in imports_dict["py_transitive_srcs"]),
      py_deps={dep[0]: _list_to_file_paths(dep[1:])
               for dep in imports_dict["py_deps"]},
      pytype_deps={dep[0]: _list_to_file_paths(dep[1:])
                   for dep in imports_dict["pytype_deps"]},
      py_deps_files=frozenset(
          FilePaths(*f) for f in imports_dict["py_deps_files"]),
      pytype_deps_files=frozenset(
          FilePaths(*f) for f in imports_dict["pytype_deps_files"]),
      transitive_inputs=frozenset(
          FilePaths(*f) for f in imports_dict["transitive_inputs"]),
      )
  # Program sanity check: anything in imports_dict that wasn't processed
  # (this catches some typos, but not all)
  if set(imports_dict) > set(vars(imports_info)):
    raise ValueError("Unprocessed keys in imports_dict: %r" % sorted(
        set(imports_dict) - set(vars(imports_info))))
  return imports_info


def _list_to_file_paths(items):
  """Make FilePaths list from linear list of short_path, path, ..."""
  return [FilePaths(short_path=short_path, path=path)
          for short_path, path in zip(items[0::2], items[1::2])]
