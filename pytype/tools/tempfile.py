import tempfile
import sys
import os
from . import path_tools


# Windows Cannot open a temp file twice without delete=False"""
if sys.platform == 'win32':
  class NamedTemporaryFile:
    # pylint: disable=W0622
    def __init__(self, mode='w+b', buffering=-1, encoding=None,
            newline=None, suffix=None, prefix=None,
            dir=None, delete=True):
      # pylint: disable=R1732
      self._tempfile = tempfile.NamedTemporaryFile(
        mode=mode, buffering=buffering, encoding=encoding,
        newline=newline, suffix=suffix, prefix=prefix, dir=dir,
        delete=False)
      self._delete = delete

    def __enter__(self):
      return self._tempfile.__enter__()

    def __exit__(self, *args, **kwargs):
      self._tempfile.__exit__(*args, **kwargs)
      if self._delete:
        os.remove(self._tempfile.name)

    def write(self, s):
      return self._tempfile.write(s)

    def read(self, n):
      return self._tempfile.read(n)

    def seek(self, *args, **kwargs):
      return self._tempfile.seek(*args, **kwargs)

    def close(self):
      return self._tempfile.close()

    @property
    def name(self):
      return self._tempfile.name

  def mkdtemp(*args, **kwargs):
    return path_tools.standardize_return_path(
      tempfile.mkdtemp(*args, **kwargs))
else:
  NamedTemporaryFile = tempfile.NamedTemporaryFile
  mkdtemp = tempfile.mkdtemp
