# Directives and annotations

<!--*
freshness: { owner: 'mdemello' reviewed: '2020-08-04' }
*-->

<!--ts-->
   * [Directives and annotations](#directives-and-annotations)
      * [Overview](#overview)
      * [Director](#director)

<!-- Added by: rechen, at: 2020-08-29T02:25-07:00 -->

<!--te-->

## Overview

Pytype accepts directives in the form of python comments, both typecomments like

```python
  x = []  # type: List[int]
```

and error disabling

```python
  x = f(a, b)  # pytype: disable=wrong-arg-types
```

We also support range-based disabling:

```python
  # pytype: disable=attribute-error
  x.foo()
  x.bar()
  # pytype: enable=attribute-error
```

Since the main pytype loop operates on bytecode, which does not contain
comments, we have a preprocessing pass to collect these comments and later merge
them with the corresponding line numbers in the bytecode.

## Director

`directors.py` defines a `Director` class, which scans a source file line by
line, extracting and storing source level information for the main `vm.py` code
to use when analysing the program.

Note: The Director is also the best place to collect other information that needs
access to the source code rather than the bytecode, e.g. variable annotations,
class and method decorators, and docstrings. See `Director.__init__` for a full
list of all the data collected.

The Director is instantiated at the start of the main loop, in
`vm.py/VirtualMachine::run_program()`, and can typically be accessed via
`vm.director` anywhere the `vm` object is available. The rest of the code uses
the director in two ways:

1. Directly accessing the stored tables, e.g `director.decorators` and `director.annotations`, all of which are indexed by line number
2. Calling `director.should_report_error()` to check if an error has been disabled

The latter method is needed because error disabling is range based, so checking
is not as simple as `if line_number in director.disables`
