"""Pickle file loading and saving."""

import gzip
import pickle
import sys

from pytype.pytd import serialize_ast


_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL
_PICKLE_RECURSION_LIMIT_AST = 40000


class LoadPickleError(Exception):
  """Errors when loading a pickled pytd file."""

  def __init__(self, filename):
    self.filename = filename
    msg = f"Error loading pickle file: {filename}"
    super().__init__(msg)


def _LoadPickle(f, filename):
  """Load a pickle file, raising a custom exception on failure."""
  try:
    return pickle.load(f)
  except Exception as e:  # pylint: disable=broad-except
    raise LoadPickleError(filename) from e


def LoadPickle(filename, compress=False, open_function=open):
  with open_function(filename, "rb") as fi:
    if compress:
      with gzip.GzipFile(fileobj=fi) as zfi:
        return _LoadPickle(zfi, filename)
    else:
      return _LoadPickle(fi, filename)


def SavePickle(data, filename=None, compress=False, open_function=open):
  """Pickle the data."""
  recursion_limit = sys.getrecursionlimit()
  sys.setrecursionlimit(_PICKLE_RECURSION_LIMIT_AST)
  assert not compress or filename, "gzip only supported with a filename"
  try:
    if compress:
      with open_function(filename, mode="wb") as fi:
        # We blank the filename and set the mtime explicitly to produce
        # deterministic gzip files.
        with gzip.GzipFile(filename="", mode="wb",
                           fileobj=fi, mtime=1.0) as zfi:
          # TODO(b/173150871): Remove disable once typeshed bug is fixed.
          pickle.dump(data, zfi, _PICKLE_PROTOCOL)  # pytype: disable=wrong-arg-types
    elif filename is not None:
      with open_function(filename, "wb") as fi:
        pickle.dump(data, fi, _PICKLE_PROTOCOL)
    else:
      return pickle.dumps(data, _PICKLE_PROTOCOL)
  finally:
    sys.setrecursionlimit(recursion_limit)


def StoreAst(ast, filename=None, open_function=open, is_package=False,
             src_path=None, metadata=None):
  """Loads and stores an ast to disk.

  Args:
    ast: The pytd.TypeDeclUnit to save to disk.
    filename: The filename for the pickled output. If this is None, this
      function instead returns the pickled string.
    open_function: A custom file opening function.
    is_package: Whether the module with the given ast is a package.
    src_path: Optionally, the filepath of the original source file.
    metadata: A list of arbitrary string-encoded metadata.

  Returns:
    The pickled string, if no filename was given. (None otherwise.)
  """
  out = serialize_ast.SerializeAst(ast, is_package, src_path, metadata)
  return SavePickle(out, filename, open_function=open_function)
