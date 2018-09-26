"""Representation of modules."""

import collections
import os


class Module(collections.namedtuple("_", "path target name kind")):
  """Inferred information about a module.
  Args:
    path: The path to the module, e.g., foo/.
    target: The filename relative to the path, e.g., bar/baz.py.
    name: The module name, e.g., bar.baz.
    kind: The module kind: Builtin, Direct, Local, or System.
      See https://github.com/google/importlab/blob/master/importlab/resolve.py.
  """

  def __new__(cls, path, target, name, kind=None):
    return super(Module, cls).__new__(cls, path, target, name, kind or "Local")

  @property
  def full_path(self):
    return os.path.join(self.path, self.target)


def infer_module(filename, pythonpath):
  """Convert a filename to a module relative to pythonpath.

  This method tries to deduce the module name from the pythonpath and the
  filename. This will not always be possible. (It depends on the filename
  starting with an entry in the pythonpath.)

  Args:
    filename: The filename of a Python file. E.g. "foo/bar/baz.py".
    pythonpath: The path Python uses to search for modules.

  Returns:
    A Module object.
  """
  # We want '' in our lookup path, but we don't want it for prefix tests.
  for path in filter(bool, pythonpath):
    if not path.endswith(os.sep):
      path += os.sep
    if filename.startswith(path):
      filename = filename[len(path):]
      break
  else:
    # We have not found filename relative to anywhere in pythonpath.
    path = ""
  return Module(path, filename, path_to_module_name(filename))


def path_to_module_name(filename):
  """Converts a filename into a dotted module name."""
  if os.path.dirname(filename).startswith(os.pardir):
    # Don't try to infer a module name for filenames starting with ../
    return None
  # TODO(mdemello): should we validate the extension?
  filename, _ = os.path.splitext(filename)
  module_name = filename.replace(os.path.sep, ".")
  # strip __init__ suffix
  module_name, _, _ = module_name.partition(".__init__")
  return module_name


def get_absolute_name(prefix, relative_name):
  """Joins a dotted-name prefix and a relative name.

  Args:
    prefix: A dotted name, e.g. foo.bar.baz
    relative_name: A dotted name with possibly some leading dots, e.g. ..x.y

  Returns:
    The relative name appended to the prefix, after going up one level for each
      leading dot.
      e.g. foo.bar.baz + ..hello.world -> foo.bar.hello.world
    None if the relative name has too many leading dots.
  """
  path = prefix.split(".") if prefix else []
  name = relative_name.lstrip(".")
  ndots = len(relative_name) - len(name)
  if ndots > len(path):
    return None
  prefix = "".join([p + "." for p in path[:len(path) + 1 - ndots]])
  return prefix + name


def get_package_name(module_name, is_package=False):
  """Figure out a package name for a module."""
  if module_name is None:
    return ""
  parts = module_name.split(".")
  if not is_package:
    parts = parts[:-1]
  return ".".join(parts)


def get_all_prefixes(module_name):
  """Return all the prefixes of a module name.

  e.g. x.y.z => x, x.y, x.y.z

  Args:
    module_name: module name

  Returns:
    List of prefixes
  """
  parts = module_name.split(".")
  name = parts[0]
  out = [name]
  for part in parts[1:]:
    name = ".".join([name, part])
    out.append(name)
  return out
