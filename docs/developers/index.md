# Developer guide

**Under Construction**

<!-- TODO(b/151848869):
* Add documentation for: config.py
* For completeness, mention: copybara, imports_map, blaze integration
* Add non-typegraph things to "Basic concepts" and "Important code components"
* Coordinate dev guide and CONTRIBUTING.md
  (https://github.com/google/pytype/issues/570)
-->

This documentation is for developers of and contributors to pytype. It covers:

* [tips][development-process] on suggested workflow
* how to [upgrade][python-upgrade] pytype for new Python versions,
* how to [support][supporting-features] new typing features,
* and pytype's core concepts and code layout.

<!--ts-->
   * [Developer guide](#developer-guide)
      * [Introduction](#introduction)
      * [Basic concepts](#basic-concepts)
      * [Important code components](#important-code-components)
         * [CFG](#cfg)
            * [Typegraph](#typegraph)
      * [Updating the developer guide](#updating-the-developer-guide)

<!-- Added by: rechen, at: 2020-11-23T14:36-08:00 -->

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
     / \
(2)<+   +>(4)
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
(`Binding(5, Node 2)`) and to `"a"` at Node 4 (`Binding("a", Node 4)`).
Meanwhile, `y` has only a single binding: `Binding(6, Node 3)`. The Bindings
that a Variable is connected to represent the possible values for that Variable.

Building up the CFG in this way allows pytype to perform type checking. When
pytype reaches Node 5 (`z = x.upper() + str(y)`), it queries the CFG to find
what `x` may be. Depending on the value of `some_val`, `x` could an `int` or a
`str`. Since `int` doesn't have a method called `upper`, pytype reports an
`attribute-error`, even though `str` _does_ have an `upper` method.

However, pytype is limited in what it knows. Looking at the example again, we
know that `y` won't be defined if `some_val` is `False`, which would make
`str(y)` fail. But pytype can't know for sure if `some_val` will evaluate to
`True` or `False`. Since there's a path through the CFG where `y` is defined
(`y = 6` if `some_val == True`), pytype won't report an error for `str(y)`. If
we change the condition to `if False`, so that pytype knows unambiguously that
only the code under `else:` will be executed, then pytype will report a
`name-error` on `str(y)` because there is no path through the CFG where `y` is
defined.

## Important code components

### CFG

The CFG, described above, is the core of type checking for pytype. By building a
graph of the paths of execution through a program, pytype knows which objects
are in scope and the types of those objects at any point in the program. The
source code for the CFG lives in the `typegraph/` directory. It's written in C++
for performance reasons.

(Note: there is also a Python implementation, `cfg.py` and `cfg_utils.py`, which
is no longer used and is not guaranteed to match the semantics of the C++
implementation.)

#### Typegraph

A CFG maps the paths of execution through a program; similarly, a typegraph maps
the flow of types through a program -- it's a CFG that's been enhanced with type
information. (In pytype, we use the two terms interchangeably.) `typegraph.h`
covers the classes that are used to build the typegraph. Some of them were
already mentioned earlier in Basic Concepts, namely Variables, Bindings and
Nodes (called CFGNodes here).

First is **CFGNode**, the building block of the CFG. A CFGNode corresponds to
one or more opcodes in the Python program being analyzed. As mentioned
previously, each Binding associates a Variable with a value at a particular
CFGNode.

CFGNodes may also have _conditions_. Recall the example program and CFG
discussed in Basic Concepts:

```python
if some_val:  # 1
  x = 5  # 2
  y = 6  # 3
else:
  x = "a"  # 4
z = x.upper() + str(y)  # 5
```

```
     (1)
     / \
(2)<+   +>(4)
 |         |
 v         |
(3)---+----+
      |
      v
     (5)
```

The condition of the if-statement is `some_val`, or more explicitly `some_val ==
True`. Pytype understands that the path `1 -> 2 -> 3 -> 5` can only be taken
when `some_val` evaluates to `True`, while `1 -> 4 -> 5` is taken when
`some_val` evaluates to False. This is accomplished by adding the condition to
the list of goals in a query. (Queries and goals are discussed in the [Solver]
section.)

CFGNodes may be associated with **Variables** by one or more **Bindings**. A
simple case, `x = 5`, was explained above. In more complex cases, such as `y =
m*x + b`, the Binding for `("m*x+b", n0)` is derived from several other
Bindings. This is represented by an **Origin** that explains how the Binding is
constructed. An Origin consists of two parts: the CFGNode of the Binding (`n0`,
in this case) and a **Source Set**, which contains all the Bindings that are
used to construct the Binding. In `y = m*x + b`, the Source Set is `{m, x, b}`.
The Solver uses Source Sets when deciding if a Binding is visible at a
particular node: for a Binding to be visible, all of the Bindings in its Source
Sets must also be visible.

Pytype often needs to know what Bindings are visible at a given node. "Visible"
means there is a path in the CFG to the given node from the node where the
Binding originates. Consider the example typegraph above: when checking if
`x.upper()` is valid, pytype wants to know: "is `x` visible as a `str` at node
5?" That Binding is set in node 4, and there's a path from node 4 to node 5 if
`some_val` is False. Pytype will then ask: "is `some_val` False at node 4?"
Since this is a limited example, pytype doesn't know, but it assumes that
`some_val` may be False. (And it will also assume `some_val` may be True! This
means "is `x` a `str`" and "is `x` an `int`" are both considered possible --
which is safer when we don't know the value of `some_val`.) Therefore yes, `x`
is visible as a `str` at node 5.

## Updating the developer guide

When adding a new page, link to it from the GitHub
[landing page][dev-landing-page].

Add new images to the [images directory][images-dir]. Check in both an SVG and a
PNG, and embed the latter in docs for consistent rendering.

<!-- General references -->
[dev-landing-page]: https://github.com/google/pytype/blob/master/docs/_layouts/dev_guide.html
[development-process]: process.md
[images-dir]: https://github.com/google/pytype/blob/master/docs/images/
[main-loop]: main_loop.md
[python-upgrade]: python_version_upgrades.md
[supporting-features]: features.md
[wiki-cfg]: https://en.wikipedia.org/wiki/Control-flow_graph
