# Pytype's bison files can work with bison 3.0.4. However, we set the minimum
# required version to 3.0.2 as that is the version of bison one can install
# with apt-get on the Travis Trusty VMs.
set(min_bison_version 3.0.2)
find_package(BISON ${min_bison_version})
if(NOT BISON_FOUND)
  message(FATAL_ERROR "PyType requires 'bison'. The minimum required 'bison' version is ${min_bison_version}.")
endif()

# Pytype's flex files can work with flex 2.6.1. However, we set the minimum
# required version to 2.5.35 as that is the version of flex one can install
# with apt-get on the Travis Trusty VMs.
set(min_flex_version 2.5.35)
find_package(FLEX ${min_flex_version})
if(NOT FLEX_FOUND)
  message(FATAL_ERROR "PyType requires 'flex'. The minimum required 'flex' version is ${min_flex_version}.")
endif()

# Find the python interpreter first so that Python libs corresponding to the
# version of this interpreter can be found below.
find_package(PythonInterp)
if (NOT PYTHONINTERP_FOUND)
  message(FATAL_ERROR "Python interpreter not found.")
endif()

find_package(PythonLibs)
if(NOT PYTHONLIBS_FOUND)
  message(FATAL_ERROR "PyType requires Python developer libraries (https://packages.ubuntu.com/python-dev).")
endif()

set(COPY_SCRIPT "${PROJECT_SOURCE_DIR}/build_scripts/pytype_copy.py")
set(TEST_MODULE_SCRIPT "${PROJECT_SOURCE_DIR}/build_scripts/test_module.py")
set(PYEXE_SCRIPT "${PROJECT_SOURCE_DIR}/build_scripts/pyexe.py")
set(CC_TEST_SCRIPT "${PROJECT_SOURCE_DIR}/build_scripts/run_cc_test.py")

add_compile_options("-std=c++11")

include(CMakeParseArguments)

set(ALL_TESTS_TARGET "test_all")
add_custom_target(
  ${ALL_TESTS_TARGET}
)

string(COMPARE EQUAL "${CMAKE_BUILD_TYPE}" "Debug" is_debug_build)
if(is_debug_build)
  add_definitions(-DPYTYPE_ENABLE_CPP_LOGGING)
endif(is_debug_build)

# Returns the fully qualified parent name for targets in the current source
# directory in |fq_parent_name|.
function(_gen_fq_target_parent_name fq_parent_name)
  # Strip the prefix so that names are all relative to the project root directory.
  string(REPLACE "${PROJECT_SOURCE_DIR}/" "" relative_path ${CMAKE_CURRENT_SOURCE_DIR})
  string(REPLACE "/" "." dotted_path ${relative_path})
  set(${fq_parent_name} ${dotted_path} PARENT_SCOPE)
endfunction(_gen_fq_target_parent_name fq_parent_name)

# Given a local target name in |name|, returns the fully qualified target name
# in |fq_target_name|.
function(_gen_fq_target_name name fq_target_name)
  string(FIND ${name} "." dot_location)
  if(${dot_location} GREATER "-1")
    message(FATAL_ERROR "Target name should not have a '.' in it.")
  endif()
  _gen_fq_target_parent_name(parent_fq_name)
  set(${fq_target_name} "${parent_fq_name}.${name}" PARENT_SCOPE)
endfunction(_gen_fq_target_name name fq_target_name)

# Given a |target_name| referenced from the current source directory, it
# evaluates and returns the fully qualified name of the target in
# |fq_target_name|. Note that a target name referenced from the current
# directory can either be a local target name, or a fully qualified global
# target name.
function(_eval_fq_target_name target_name fq_target_name)
  string(FIND ${target_name} "." dot_location)
  if(${dot_location} EQUAL 0)
    # This is a local target to prefix the parent name
    _gen_fq_target_parent_name(parent_name)
    set(${fq_target_name} "${parent_name}${target_name}" PARENT_SCOPE)
  else()
    # This is an absolute target so just return the target name as is.
    set(${fq_target_name} ${target_name} PARENT_SCOPE)
  endif()
endfunction(_eval_fq_target_name target_name fq_target_name)

# Given a fully qualifed target name |fq_target_name|, and a list of file names
# relative to the current directory, this function adds a list of the absolute
# paths to these files as the property "OUT" to the target.
function(_add_out_property fq_target_name relative_filename_list)
  set(absolute_filename_list "")
  foreach(src IN LISTS relative_filename_list)
    list(APPEND absolute_filename_list "${CMAKE_CURRENT_BINARY_DIR}/${src}")
  endforeach(src)

  set_target_properties(
    ${fq_target_name}
    PROPERTIES
      OUT "${absolute_filename_list}"
  )
endfunction(_add_out_property local_target_name out_file_list)

# Given a list of |targets|, the list of their "OUT" property are returned
# in a var named by |out_property_list|.
function(_get_out_property_list targets out_property_list)
  set(out_list "")
  if(targets)
    foreach(tgt IN LISTS targets)
      _eval_fq_target_name(${tgt} fq_target_name)
      list(APPEND out_list $<TARGET_PROPERTY:${fq_target_name},OUT>)
    endforeach(tgt)
  endif()
  set(${out_property_list} "${out_list}" PARENT_SCOPE)
endfunction(_get_out_property_list targets out_property_list)

# Function implementing a 'genbison' rule which invokes bison over a source
# file.
# The 'genbison' rule requires the following arguments:
# NAME - The local name of the target for this rule.
# SRC - The .yy file in the current directory.
# HDR_OUT - The name of the bison generated header file.
# CC_OUT - The name of bison generated cc file.
function(genbison)
  cmake_parse_arguments(
    GENBISON  # prefix
    ""        # optional args
    "NAME;SRC;HDR_OUT;CC_OUT"  # single value args
    ""  # multi-value args
    ${ARGN}
  )
  if(NOT GENBISON_NAME)
    message(FATAL_ERROR "'genbison' rule requries a NAME argument specifying the target name.")
  endif()
  if(NOT GENBISON_SRC)
    message(FATAL_ERROR "'genbison' rule requires a SRC argument specifying the .yy file.")
  endif()
  if(NOT GENBISON_HDR_OUT)
    message(FATAL_ERROR "'genbison' rule requries a HDR_OUT argument specifying the name of the generated header file.")
  endif()
  if(NOT GENBISON_CC_OUT)
    message(FATAL_ERROR "'genbison' rule requries a CC_OUT argument specifying the name of the generated .cc file.")
  endif()

  _gen_fq_target_name(${GENBISON_NAME} fq_target_name)
  set(CC_OUT "${CMAKE_CURRENT_BINARY_DIR}/${GENBISON_CC_OUT}")
  set(HDR_OUT "${CMAKE_CURRENT_BINARY_DIR}/${GENBISON_HDR_OUT}")
  BISON_TARGET(
    ${fq_target_name}
    "${CMAKE_CURRENT_SOURCE_DIR}/${GENBISON_SRC}"
    ${CC_OUT}
    DEFINES_FILE ${HDR_OUT}
    COMPILE_FLAGS --language=c++
  )
  # The BISON_TARGET function does not create a target.
  # So, we create a dummy target which consumes the bison output.
  add_custom_target(
    ${fq_target_name}
    ALL
    SOURCES "${BISON_${fq_target_name}_OUTPUTS}"
  )

  # We add convenience properties to the target so that properties
  # like the generated header or cc file output can be retrieved for
  # use with, say, flex targets.
  set_target_properties(
    ${fq_target_name}
    PROPERTIES
      HDR_OUT ${HDR_OUT}
      CC_OUT ${CC_OUT}
  )
endfunction(genbison)

# Function implementing a 'genflex' rule which invokes flex over a source file.
# The 'genflex' rule requires the following arguments:
# NAME - The local name of the target for this rule.
# SRC - The .lex file on which flex should be invoked.
# CC_OUT - The generated .cc file.
# BISON_DEP - The bison target whose outputs are consumed by this flex target.
function(genflex)
  cmake_parse_arguments(
    GENFLEX  # prefix
    ""       # optional args
    "NAME;SRC;CC_OUT;BISON_DEP"  # single value args
    ""  # multi-value args
    ${ARGN}
  )
  if(NOT GENFLEX_NAME)
    message(FATAL_ERROR "'genflex' rule requires a NAME argument.")
  endif()
  if(NOT GENFLEX_CC_OUT)
    message(FATAL_ERROR "'genflex' rule requires a CC_OUT argument specifying the name of the generated .cc file.")
  endif()
  if(NOT GENFLEX_BISON_DEP)
    message(FATAL_ERROR "'genflex' rule requires a BISON_DEP argument specifying the 'genbison' target whose outputs should be fed to this 'genflex' target.")
  endif()
  if(NOT GENFLEX_SRC)
    message(FATAL_ERROR "'genflex' rule requires a SRC argument specifying the .lex file")
  endif()

  _gen_fq_target_name(${GENFLEX_NAME} fq_target_name)
  set(cc_out "${CMAKE_CURRENT_BINARY_DIR}/${GENFLEX_CC_OUT}")
  FLEX_TARGET(
    ${fq_target_name}
    "${CMAKE_CURRENT_SOURCE_DIR}/${GENFLEX_SRC}"
    ${cc_out}
  )
  add_custom_target(
    ${fq_target_name}
    ALL
    SOURCES "${FLEX_${fq_target_name}_OUTPUTS}"
  )
  # Add the bison target as a dependency to this flex target so that
  # the bison outputs are ready before flex is run.
  _eval_fq_target_name(${GENFLEX_BISON_DEP} fq_bison_target_name)
  add_dependencies(${fq_target_name} ${fq_bison_target_name})
  set_target_properties(
    ${fq_target_name}
    PROPERTIES
      CC_OUT ${cc_out}
  )
endfunction(genflex)

# A function implementing a 'cc_library' rule which builds a C++ static library.
# The 'cc_library' rule takes the following arguments:
# NAME - The name of the target. This is a required argument.
# SRCS - List of .cc files of the library. This is a required argument.
# HDRS - List of .h files of the library.
# DEPS - Other cc_library targets this library depends on.
#
# TODO(sivachandra): Implement a header only library rule.
# CMake does not support header only libraries via its builtin utilities. Since
# Pytype uses header only library targets, having rules to setup header only
# library targets helps in setting up the dependencies correctly.
function(cc_library)
  cmake_parse_arguments(
    CC_LIBRARY        # prefix
    ""                # optional args
    "NAME"            # single value args
    "SRCS;HDRS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT CC_LIBRARY_NAME)
    message(FATAL_ERROR "'cc_library' rule requires a NAME argument.")
  endif()

  _gen_fq_target_name(${CC_LIBRARY_NAME} fq_target_name)

  add_library(
    ${fq_target_name}
    ${CC_LIBRARY_SRCS}
    ${CC_LIBRARY_HDRS}
  )

  target_include_directories(
    ${fq_target_name}
    PUBLIC
      ${PYTHON_INCLUDE_DIRS}
      ${PROJECT_SOURCE_DIR}
  )

  set_target_properties(
    ${fq_target_name}
    PROPERTIES
      LINKER_LANGUAGE CXX
      OUTPUT_NAME ${CC_LIBRARY_NAME}
  )

  if(CC_LIBRARY_DEPS)
    foreach(dep IN LISTS CC_LIBRARY_DEPS)
      _eval_fq_target_name(${dep} fq_dep_name)
      target_link_libraries(${fq_target_name} ${fq_dep_name})
    endforeach(dep)
  endif(CC_LIBRARY_DEPS)
endfunction(cc_library)

# A function implementing a 'cc_test' rule which builds a C++ test suite binary
# and runs it.
# The 'cc_test' rule takes the following arguments:
# NAME - The name of the target. This is a required argument.
# SRCS - List of .cc files of the test. This is a required argument.
# DEPS - List of cc_library targets this test depends on.
function(cc_test)
  cmake_parse_arguments(
    CC_TEST      # prefix
    ""           # optional args
    "NAME"       # single value args
    "SRCS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT CC_TEST_NAME)
    message(FATAL_ERROR "'cc_test' rule requires a NAME argument.")
  endif()
  if(NOT CC_TEST_SRCS)
    message(FATAL_ERROR "'cc_test' rule requires a SRCS argument specifying the list of .cc files of the test.")
  endif()

  _gen_fq_target_name("${CC_TEST_NAME}___runner_internal" fq_runner_target_name)
  _gen_fq_target_name(${CC_TEST_NAME} fq_target_name)

  add_executable(
    ${fq_runner_target_name}
    ${CC_TEST_SRCS}
  )

  target_include_directories(
    ${fq_runner_target_name}
    PUBLIC
      ${PYTHON_INCLUDE_DIRS}
      ${PROJECT_SOURCE_DIR}
      ${PROJECT_SOURCE_DIR}/googletest/googlemock/include
      ${PROJECT_SOURCE_DIR}/googletest/googletest/include
  )

  if(CC_TEST_DEPS)
    foreach(dep IN LISTS CC_TEST_DEPS)
      _eval_fq_target_name(${dep} fq_dep_name)
      target_link_libraries(${fq_runner_target_name} ${fq_dep_name})
    endforeach(dep)
  endif()

  target_link_libraries(
    ${fq_runner_target_name}
    ${PYTHON_LIBRARIES}
    gtest_main
    gmock_main
  )

  # Add a target to run the executable built above.
  set_target_properties(
    ${fq_runner_target_name}
    PROPERTIES
      PREFIX ""
      SUFFIX ".exe"
      OUTPUT_NAME "${CC_TEST_NAME}"
  )

  set(log_file "${CC_TEST_NAME}.log")
  add_custom_command(
    OUTPUT ${log_file}
    COMMAND ${CC_TEST_SCRIPT} -t ${fq_target_name} -b "${CMAKE_CURRENT_BINARY_DIR}/${CC_TEST_NAME}.exe" -l "${CMAKE_CURRENT_BINARY_DIR}/${log_file}"
    DEPENDS ${fq_runner_target_name}
  )

  add_custom_target(
    ${fq_target_name}
    DEPENDS ${log_file}
  )

  add_dependencies(${ALL_TESTS_TARGET} ${fq_target_name})
endfunction(cc_test)

# Function implementing a rule 'py_extension' to compile a set of CC and headers
# files into a Python extension module.
# The 'py_extension' rule requires the following arguments:
# NAME - The local name of the target.
# SRCS - A list of sources which have to be compiled in to a Python extension
#        module.
#
# The rule also takes an optionl DEPS argument which is the list of targets
# on which this 'py_extension' target depends.
function(py_extension)
  cmake_parse_arguments(
    PY_EXTENSION  # prefix
    ""
    "NAME"  # single value args
    "SRCS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT PY_EXTENSION_NAME)
    message(FATAL_ERROR "'py_extension' rule requires a NAME argument.")
  endif()
  if(NOT PY_EXTENSION_SRCS)
    message(FATAL_ERROR "'py_extension' rule requires a SRCS argument.")
  endif()

  _gen_fq_target_name(${PY_EXTENSION_NAME} fq_target_name)
  add_library(
    ${fq_target_name}
    SHARED  # We want a py_extension library to be an shared library
    ${PY_EXTENSION_SRCS}
  )
  set_target_properties(
    ${fq_target_name}
    PROPERTIES
      PREFIX ""
      OUTPUT_NAME ${PY_EXTENSION_NAME}
  )
  target_include_directories(
    ${fq_target_name}
    PRIVATE
      ${PYTHON_INCLUDE_DIRS}
      ${PROJECT_SOURCE_DIR}
      ${PROJECT_BINARY_DIR}
      ${CMAKE_CURRENT_BINARY_DIR}
      ${CMAKE_CURRENT_SOURCE_DIR}
  )
  target_link_libraries(
    ${fq_target_name}
    ${PYTHON_LIBRARIES}
  )
  # Add the deps if specified
  if(PY_EXTENSION_DEPS)
    foreach(dep IN LISTS PY_EXTENSION_DEPS)
      _eval_fq_target_name(${dep} fq_dep_name)
      add_dependencies(${fq_target_name} ${fq_dep_name})
    endforeach(dep)
  endif()
endfunction(py_extension)

function(py_library)
  cmake_parse_arguments(
    PY_LIBRARY   # prefix
    ""           # optional args
    "NAME"       # single value args
    "SRCS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT PY_LIBRARY_NAME)
    message(FATAL_ERROR "'py_library' rule requires a NAME argument.")
  endif()

  _get_out_property_list("${PY_LIBRARY_DEPS}" deps_out)

  if(PY_LIBRARY_SRCS)
    # Add a command which copies the listed sources over to the current build
    # directory.
    add_custom_command(
      OUTPUT ${PY_LIBRARY_SRCS}
      COMMAND ${PYTHON_EXECUTABLE} -B ${COPY_SCRIPT} -s ${CMAKE_CURRENT_SOURCE_DIR} -d ${CMAKE_CURRENT_BINARY_DIR} ${PY_LIBRARY_SRCS}
      DEPENDS ${PY_LIBRARY_SRCS} ${deps_out}
    )
  endif()

  _gen_fq_target_name(${PY_LIBRARY_NAME} fq_target_name)
  add_custom_target(
    ${fq_target_name}
    ALL
    DEPENDS ${PY_LIBRARY_SRCS}
  )
  # Add the deps if specified
  if(PY_LIBRARY_DEPS)
    foreach(dep IN LISTS PY_LIBRARY_DEPS)
      _eval_fq_target_name(${dep} fq_dep_name)
      add_dependencies(${fq_target_name} ${fq_dep_name})
    endforeach(dep)
  endif()

  _add_out_property(${fq_target_name} "${PY_LIBRARY_SRCS}")
endfunction(py_library)

function(toplevel_py_binary)
  cmake_parse_arguments(
    PY_BINARY    # prefix
    ""           # optional args
    "NAME;MAIN"  # single value args
    "SRCS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT PY_BINARY_NAME)
    message(FATAL_ERROR "'py_binary' rule requires a NAME argument.")
  endif()
  if(NOT PY_BINARY_SRCS)
    message(FATAL_ERROR "'py_binary' rule requires a SRCS argument.")
  endif()
  if(NOT PY_BINARY_MAIN)
    message(FATAL_ERROR "'py_binary' rule requires a MAIN argument.")
  endif()

  if(PY_BINARY_DEPS)
    set(deps "DEPS ${PY_BINARY_DEPS}")
  endif()

  set(lib_suffix "___internal_py_library_for_binary")
  set(py_binary_library_name ${PY_BINARY_NAME}${lib_suffix})

  py_library(
    NAME
      ${py_binary_library_name}
    SRCS
      ${PY_BINARY_SRCS}
    DEPS
      ${PY_BINARY_DEPS}
  )
  _gen_fq_target_name(${py_binary_library_name} py_binary_library_fq_name)
  _get_out_property_list(${py_binary_library_fq_name} out_file_list)

  string(REPLACE "${PROJECT_SOURCE_DIR}/" "" relative_path_to_main ${CMAKE_CURRENT_SOURCE_DIR}/${PY_BINARY_MAIN})
  string(REPLACE ".py" "" relative_path_to_main_no_ext ${relative_path_to_main})
  string(REPLACE "/" "." main_module ${relative_path_to_main_no_ext})

  set(exe_path ${PYTYPE_OUT_BIN_DIR}/${PY_BINARY_NAME})

  # Copy the main script to a file with the name of the target name.
  add_custom_command(
      OUTPUT ${exe_path}
      COMMAND ${PYTHON_EXECUTABLE} ${PYEXE_SCRIPT} -p ${PROJECT_BINARY_DIR} -v TYPESHED_HOME=${PROJECT_SOURCE_DIR}/typeshed -m ${main_module} -x ${exe_path}
      DEPENDS ${out_file_list}  # This command should run if the internal py_library was built.
  )
  _gen_fq_target_name(${PY_BINARY_NAME} fq_target_name)
  add_custom_target(
    ${fq_target_name}
    ALL
    DEPENDS ${exe_path}
  )
endfunction(toplevel_py_binary)

function(py_test)
  cmake_parse_arguments(
    PY_TEST      # prefix
    ""           # optional args
    "NAME"       # single value args
    "SRCS;DEPS"  # multi-value args
    ${ARGN}
  )
  if(NOT PY_TEST_NAME)
    message(FATAL_ERROR "'py_test' rule requires a NAME argument.")
  endif()

  _gen_fq_target_name(${PY_TEST_NAME} fq_target_name)
  set(lib_suffix "___internal_py_library_for_test")

  py_library(
    NAME
      "${PY_TEST_NAME}${lib_suffix}"
    SRCS
      ${PY_TEST_SRCS}
    DEPS
      ${PY_TEST_DEPS}
  )

  _get_out_property_list(${fq_target_name}${lib_suffix} lib_out)

  add_custom_command(
    OUTPUT ${PY_TEST_NAME}.log
    COMMAND "TYPESHED_HOME=${PROJECT_SOURCE_DIR}/typeshed" ${PYTHON_EXECUTABLE} -B
            ${TEST_MODULE_SCRIPT} ${fq_target_name} -o ${CMAKE_CURRENT_BINARY_DIR}/${PY_TEST_NAME}.log -P ${PROJECT_BINARY_DIR} -s -p
    DEPENDS ${lib_out}
  )
  add_custom_target(
    ${fq_target_name}
    DEPENDS ${PY_TEST_NAME}.log
  )
  # The internal py_library target should be a dep for this target.
  add_dependencies(${fq_target_name} "${fq_target_name}${lib_suffix}")

  # Add the deps if specified
  if(PY_TEST_DEPS)
    foreach(dep IN LISTS PY_TEST_DEPS)
      _eval_fq_target_name(${dep} fq_dep_name)
      add_dependencies(${fq_target_name} ${fq_dep_name})
    endforeach(dep)
  endif()

  add_dependencies(${ALL_TESTS_TARGET} ${fq_target_name})
endfunction(py_test)

function(filegroup)
  cmake_parse_arguments(
    FILEGROUP  # prefix
    ""  # optional args
    "NAME"  # single value args
    "SRCS"  # multi-value args
    ${ARGN}
  )
  if(NOT FILEGROUP_NAME)
    message(FATAL_ERROR "'filegroup' rule requires a NAME argument.")
  endif()
  if(NOT FILEGROUP_SRCS)
    message(FATAL_ERROR "'filegroup' rule requires a SRCS argument.")
  endif()

  # Add a command which copies the listed sources over to the current build
  # directory.
  add_custom_command(
    OUTPUT ${FILEGROUP_SRCS}
    COMMAND ${PYTHON_EXECUTABLE} -B ${COPY_SCRIPT} -s ${CMAKE_CURRENT_SOURCE_DIR} -d ${CMAKE_CURRENT_BINARY_DIR} ${FILEGROUP_SRCS}
    DEPENDS ${FILEGROUP_SRCS}
  )

  _gen_fq_target_name(${FILEGROUP_NAME} fq_target_name)
  add_custom_target(
    ${fq_target_name}
    ALL
    DEPENDS ${FILEGROUP_SRCS}
  )
endfunction(filegroup)

# Add an __init__.py file to the current binary directory.
# TODO(sivachandra): Make this rule use the __init__.py from the current source
# directory if present. Currently, none of Pytype's __init__.py files have any
# functionality. So, just creating an empty __init__.py is sufficient.
function(add_package)
  # TODO(sivachandra): Make this function create a real target on which all
  # py_library targets in the directory will implicitly depend on.
  file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/__init__.py" "\n")
endfunction(add_package)
