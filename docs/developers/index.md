# Developer guide

**Under Construction**

This documentation is for developers of and contributors to pytype. It covers
[tips][development-process] on suggested workflow, how to
[upgrade][python-upgrade] pytype for new Python versions, and pytype's core
concepts and code layout.

<!--ts-->
   * [Developer guide](#developer-guide)
      * [Introduction](#introduction)
      * [Basic concepts](#basic-concepts)
      * [Adding a new feature](#adding-a-new-feature)
      * [Important code components](#important-code-components)
         * [AST representation of type stubs](#ast-representation-of-type-stubs)
            * [Where stubs are located](#where-stubs-are-located)
         * [Abstract representation of types](#abstract-representation-of-types)
         * [Conversion between representations](#conversion-between-representations)
         * [Bytecode handling](#bytecode-handling)
         * [CFG](#cfg)

<!-- Added by: mdemello, at: 2020-05-21T16:31-07:00 -->

<!--te-->

## Introduction

Pytype is built around a "shadow bytecode interpreter", which traces through a
program's bytecode, mimicking the effects of the cpython interpreter but
tracking types rather than values.

A good starting point is to trace through the details of [pytype's main
loop][main-loop] and get a feel for how the bytecode interpreter works.

## Basic concepts

As pytype analyzes a program, it builds a [control flow graph][wiki-cfg] (CFG)
that represents how the parts of the program work together. Each **Node** in the
CFG roughly correlates with a single statement in the program.

For example:

```python
if some_val:  # 1
  x = 5  # 2
  y = 6  # 3
else:
  x = "a"  # 4
z = x.upper() + str(y)  # 5
```

This program has a CFG that looks like:

```
     (1)
     | |
(2)<-+ +->(4)
 |         |
 v         |
(3)---+----+
      |
      v
     (5)
```

Note how the two branches of the if-else statement are represented by two paths
starting at Node 1 and coming together at Node 5.

A **Variable** tracks the type information for a variable in the program being
analyzed. This includes simple variables (e.g. `x` in `x = 5`), function
arguments (`a` and `b` in `def f(a, b)`), and functions, classes and modules.

A **Binding** associates a Variable with a value at a particular Node. In the
example above, the Variable for `x` is bound to the value `5` at Node 2
(`Binding(5, Node 2)`) and to `"a"` at Node 4. (`Binding("a", Node 4)`).
Meanwhile, `y` has only a single `Binding(6, Node 3)`.

Building up the CFG in this way allows pytype to perform type checking. When
pytype reaches Node 5 (`z = x.upper()`), it queries the CFG to find what `x` may
be. Depending on the value of `some_val`, `x` could an `int` or a `str`. Since
`int` doesn't have a method called `upper`, pytype reports an `attribute-error`,
even though `str` _does_ have an `upper` method.

However, pytype is limited by what it knows. Looking at the example again, we
know that `y` won't be defined if `some_val` is `False`, which would make
`str(y)` fail. But pytype can't know for sure if `some_val` will evaluate to
`True` or `False`. Since there's a path through the CFG where `y` is defined
(`y = 6` if `some_val == True`), pytype won't report an error for `str(y)`. If
we change the condition to `if False`, so that pytype knows unambiguously that
only the code under `else:` will be executed, then pytype will report a
`name-error` on `str(y)` because there is no path through the CFG where `y` is
defined.

## Adding a new feature

pytd node, abstract value, conversion both ways

## Important code components

### AST representation of type stubs

`pyi/` (parser), `pytd/`

#### Where stubs are located

typeshed, `pytd/builtins/`, `pytd/stdlib/`,
`//devtools/python/blaze/pytype/overrides/`

### Abstract representation of types

`abstract.py`, `matcher.py`, `overlays/`

### Conversion between representations

`convert.py`, `output.py`

### Bytecode handling

`pyc/`, `vm.py`

### CFG

`typegraph/`

<!-- General references -->
[development-process]: process.md
[main-loop]: main_loop.md
[python-upgrade]: python_version_upgrades.md
[wiki-cfg]: https://en.wikipedia.org/wiki/Control-flow_graph
