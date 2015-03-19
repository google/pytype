# This file corresponds to the example in the "workflow" document.

class ConfigParser:
  def __init__(self, filename):
    self.filename = filename
  # TODO(pludemann): this is the actual example in the document, but
  #                  it doesn't work:
  def read(self):
    with open(self.filename, "r") as fi:
      return fi.read()
  # TODO(pludemann): this does work:
  # def read(self):
  #   fi = open(self.filename, "r")
  #   return fi.read()

# TODO(pludemann): other things to test:
#                  for a, b in zip(...)
#                  for a, b in generate_matches(...)  [in pytree.py]

# TODO(pludemann): remove the following note-to-self for debugging:

# import dis
# print 'ConfigParser.__init__'
# dis.dis(ConfigParser.__init__)
# print
# print 'ConfigParser.read'
# dis.dis(ConfigParser.read)
#
# ConfigParser.__init__
#   3           0 LOAD_FAST                1 (filename)
#               3 LOAD_FAST                0 (self)
#               6 STORE_ATTR               0 (filename)
#               9 LOAD_CONST               0 (None)
#              12 RETURN_VALUE
#
# ConfigParser.read
#   5           0 LOAD_GLOBAL              0 (open)
#               3 LOAD_FAST                0 (self)
#               6 LOAD_ATTR                1 (filename)
#               9 LOAD_CONST               1 ('r')
#              12 CALL_FUNCTION            2
#              15 SETUP_WITH              17 (to 35)
#              18 STORE_FAST               1 (fi)
#
#   6          21 LOAD_FAST                1 (fi)
#              24 LOAD_ATTR                2 (read)
#              27 CALL_FUNCTION            0
#              30 RETURN_VALUE
#              31 POP_BLOCK
#              32 LOAD_CONST               0 (None)
#         >>   35 WITH_CLEANUP
#              36 END_FINALLY
#              37 LOAD_CONST               0 (None)
#              40 RETURN_VALUE
#
