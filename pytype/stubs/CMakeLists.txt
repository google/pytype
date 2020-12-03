add_package()

# CMake does not do dependency tracking if files are listed by a GLOB operation.
# So, we have to list the files individually as we want them to be tracked as
# build inputs.
filegroup(
  NAME
    stubs
  SRCS
    builtins/2/__builtin__.pytd
    builtins/2/array.pytd
    builtins/2/attr/__init__.pytd
    builtins/2/attr/_compat.pytd
    builtins/2/attr/_config.pytd
    builtins/2/attr/_funcs.pytd
    builtins/2/attr/_make.pytd
    builtins/2/attr/converters.pytd
    builtins/2/attr/exceptions.pytd
    builtins/2/attr/filters.pytd
    builtins/2/attr/setters.pytd
    builtins/2/attr/validators.pytd
    builtins/2/mypy_extensions.pytd
    builtins/2/numpy/__init__.pytd
    builtins/2/protocols.pytd
    builtins/2/typing.pytd

    builtins/2and3/array.pytd
    builtins/2and3/attr/__init__.pytd
    builtins/2and3/attr/_compat.pytd
    builtins/2and3/attr/_config.pytd
    builtins/2and3/attr/_funcs.pytd
    builtins/2and3/attr/_make.pytd
    builtins/2and3/attr/converters.pytd
    builtins/2and3/attr/exceptions.pytd
    builtins/2and3/attr/filters.pytd
    builtins/2and3/attr/setters.pytd
    builtins/2and3/attr/validators.pytd
    builtins/2and3/mypy_extensions.pytd
    builtins/2and3/numpy/__init__.pytd
    builtins/2and3/protocols.pytd
    builtins/2and3/typing.pytd

    builtins/3/__builtin__.pytd
    builtins/3/array.pytd
    builtins/3/attr/__init__.pytd
    builtins/3/attr/_compat.pytd
    builtins/3/attr/_config.pytd
    builtins/3/attr/_funcs.pytd
    builtins/3/attr/_make.pytd
    builtins/3/attr/converters.pytd
    builtins/3/attr/exceptions.pytd
    builtins/3/attr/filters.pytd
    builtins/3/attr/setters.pytd
    builtins/3/attr/validators.pytd
    builtins/3/builtins.pytd
    builtins/3/mypy_extensions.pytd
    builtins/3/numpy/__init__.pytd
    builtins/3/protocols.pytd
    builtins/3/typing.pytd

    stdlib/2/_ctypes.pytd
    stdlib/2/collections.pytd
    stdlib/2/dummy_thread.pytd
    stdlib/2/encodings.pytd

    stdlib/2and3/_ctypes.pytd
    stdlib/2and3/collections.pytd
    stdlib/2and3/dummy_thread.pytd
    stdlib/2and3/encodings.pytd

    stdlib/3/_ctypes.pytd
    stdlib/3/collections.pytd
    stdlib/3/dummy_thread.pytd
    stdlib/3/encodings.pytd
    stdlib/3/enum.pytd
)
