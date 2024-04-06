"""Global VM context.

Add global state that should be shared by all frames, abstract values, etc. to
the Context object. Make sure to add only things that are truly global! The
context introduces circular dependencies that degrade the quality of typing,
cross references, and other tooling.

New Context attributes should also be added to the ContextType protocol in
abstract/base.py.
"""

from typing import Optional

from pytype import config
from pytype import load_pytd
from pytype.errors import errors
from pytype.rewrite import convert
from pytype.rewrite import load_abstract
from pytype.rewrite import output
from pytype.rewrite import pretty_printer


class Context:
  """Global VM context."""

  # TODO(b/241479600): We have to duplicate the instance attributes here to work
  # around a weird bug in current pytype. Once rewrite/ is rolled out, this bug
  # will hopefully be gone and we can delete these duplicate declarations.
  options: config.Options
  pytd_loader: load_pytd.Loader

  errorlog: errors.VmErrorLog
  abstract_converter: convert.AbstractConverter
  abstract_loader: load_abstract.AbstractLoader
  pytd_converter: output.PytdConverter
  consts: load_abstract.Constants

  def __init__(
      self,
      options: Optional[config.Options] = None,
      pytd_loader: Optional[load_pytd.Loader] = None,
  ):
    self.options = options or config.Options.create()
    self.pytd_loader = pytd_loader or load_pytd.create_loader(self.options)

    self.errorlog = errors.VmErrorLog(pretty_printer.PrettyPrinter(self))
    self.abstract_converter = convert.AbstractConverter(self)
    self.abstract_loader = load_abstract.AbstractLoader(self, self.pytd_loader)
    self.pytd_converter = output.PytdConverter(self)

    # We access these all the time, so create a convenient alias.
    self.consts = self.abstract_loader.consts
