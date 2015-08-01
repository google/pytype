"""VM representation of Python exceptions."""


class ByteCodeException(Exception):
  """A wrapper for VM exceptions, to distinguish them from real exceptions."""

  def __init__(self, exception_type, message):
    # Exception is an old-style class, so can't use super.
    # super(ByteCodeException, self).__init__(message)
    Exception.__init__(self, message)
    self.exception_type = exception_type

  def create_instance(self):
    """Instantiate an instance of the inner exception."""
    return self.exception_type(self.message)


class ByteCodeIndexError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, IndexError, message)


class ByteCodeValueError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, ValueError, message)


class ByteCodeAssertionError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, AssertionError, message)


class ByteCodeAttributeError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, AttributeError, message)


class ByteCodeUnboundLocalError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, UnboundLocalError, message)


class ByteCodeNameError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, NameError, message)


class ByteCodeKeyError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, KeyError, message)


class ByteCodeTypeError(ByteCodeException):

  def __init__(self, message):
    ByteCodeException.__init__(self, TypeError, message)
