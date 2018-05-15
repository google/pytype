set(min_bison_version 3.0.4)
find_package(BISON ${min_bison_version})
if(NOT BISON_FOUND)
  message(FATAL_ERROR "PyType requires 'bison'. The minimum required 'bison' version is ${min_bison_version}.")
endif()

set(min_flex_version 2.6.1)
find_package(FLEX ${min_flex_version})
if(NOT FLEX_FOUND)
  message(FATAL_ERROR "PyType requires 'flex'. The minimum required 'flex' version is ${min_flex_version}.")
endif()

find_package(PythonLibs)
if(NOT PYTHONLIBS_FOUND)
  message(FATAL_ERROR "PyType requires Python developer libraries (https://packages.ubuntu.com/python-dev).")
endif()

add_compile_options("-std=c++11")

include(CMakeParseArguments)

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
