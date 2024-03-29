add_package()

py_library(
  NAME
    imports
  DEPS
    .base
    .builtin_stubs
    .init
    .module_loader
    .pickle_utils
    .typeshed
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
    .pickle_utils
    pytype.config
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.pyi.parser
)

py_library(
  NAME
    builtin_stubs
  SRCS
    builtin_stubs.py
  DEPS
    .base
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.pyi.parser
    pytype.pytd.pytd
)

py_library(
  NAME
    typeshed
  SRCS
    typeshed.py
  DEPS
    .base
    .builtin_stubs
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.pyi.parser
)

py_library(
  NAME
    pickle_utils
  SRCS
    pickle_utils.py
  DEPS
    pytype.pytd.pytd
)

py_library(
  NAME
    serde_utils_api
  SRCS
    pickle_utils.py
  DEPS
    pytype.pytd.pytd
)

py_test(
  NAME
    builtin_stubs_test
  SRCS
    builtin_stubs_test.py
  DEPS
    .builtin_stubs
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.pyi.parser
    pytype.pytd.pytd
    pytype.tests.test_base
)

py_test(
  NAME
    typeshed_test
  SRCS
    typeshed_test.py
  DEPS
    .builtin_stubs
    .typeshed
    pytype.utils
    pytype.platform_utils.platform_utils
    pytype.pytd.parse.parser_test_base
    pytype.tests.test_base
)
