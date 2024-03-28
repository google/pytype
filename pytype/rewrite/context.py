"""Global VM context.

Add global state that should be shared by all frames, abstract values, etc. to
the Context object. Make sure to add only things that are truly global! The
context introduces circular dependencies that degrade the quality of typing,
cross references, and other tooling.

New Context attributes should also be added to the ContextType protocol in
abstract/base.py and FakeContext in abstract/test_utils.py.
"""

from pytype.errors import errors
from pytype.rewrite import output
from pytype.rewrite import pretty_printer
from pytype.rewrite.abstract import abstract


class Context:
  """Global VM context."""

  # TODO(b/241479600): We have to duplicate the instance attributes here to work
  # around a weird bug in current pytype. Once rewrite/ is rolled out, this bug
  # will hopefully be gone and we can delete these duplicate declarations.
  ANY: abstract.Singleton
  BUILD_CLASS: abstract.Singleton
  NULL: abstract.Singleton

  errorlog: errors.VmErrorLog
  pytd_converter: output.PyTDConverter

  def __init__(self):
    # Singleton abstract values. Conceptually, they are constants.
    # pylint: disable=invalid-name
    self.ANY = abstract.Singleton(self, 'ANY')
    self.BUILD_CLASS = abstract.Singleton(self, 'BUILD_CLASS')
    self.NULL = abstract.Singleton(self, 'NULL')
    # pylint: enable=invalid-name

    self.errorlog = errors.VmErrorLog(pretty_printer.PrettyPrinter(self))
    self.pytd_converter = output.PyTDConverter(self)
