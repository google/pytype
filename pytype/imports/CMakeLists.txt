add_package()

py_library(
  NAME
    imports
  DEPS
    .base
    .init
    .module_loader
)

py_library(
  NAME
    init
  SRCS
    __init__.py
)

py_library(
  NAME
    base
  SRCS
    base.py
  DEPS
    pytype.pytd.pytd
)

py_library(
  NAME
    module_loader
  SRCS
    module_loader.py
  DEPS
    .base
    pytype.config
    pytype.platform_utils.platform_utils
    pytype.pyi.parser
    pytype.pytd.pytd
)
