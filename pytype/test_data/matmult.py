# Tests python 3.5 opcodes
#   BINARY_MATRIX_MULTIPLY
#   INPLACE_MATRIX_MULTIPLY

class Matrix():
  def __matmul__(self, other):
    return self

a = Matrix()
b = Matrix()
c = a @ b
a @= b
