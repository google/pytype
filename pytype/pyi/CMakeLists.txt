add_package()

genbison(
  NAME
    parser_gen
  SRC
    parser.yy
  HDR_OUT
    parser.tab.hh
  CC_OUT
    parser.tab.cc
)

genflex(
  NAME
    lexer
  SRC
    lexer.lex
  CC_OUT
    lexer.lex.cc
  BISON_DEP
    .parser_gen
)

py_extension(
  NAME
    parser_ext
  SRCS
    parser_ext.cc
    $<TARGET_PROPERTY:pytype.pyi.lexer,CC_OUT>
    $<TARGET_PROPERTY:pytype.pyi.parser_gen,CC_OUT>
    $<TARGET_PROPERTY:pytype.pyi.parser_gen,HDR_OUT>
  DEPS
    .parser_gen
    .lexer
)
