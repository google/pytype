# Developer guide

<!--* freshness: { owner: 'rechen' reviewed: '2020-12-08' } *-->

This documentation is for developers of and contributors to pytype. It covers
pytype's core concepts and code layout, as well as tips on suggested workflow.

<!--ts-->
   * [Developer guide](#developer-guide)
      * [Contributing](#contributing)
      * [Introduction](#introduction)
      * [Basic concepts](#basic-concepts)
      * [Updating the developer guide](#updating-the-developer-guide)

<!-- Added by: mdemello, at: 2021-07-27T17:51-07:00 -->

<!--te-->

## Contributing

To get started with contributing to pytype, we recommend familiarizing yourself
with the codebase and workflow by fixing a small issue. See the
[Issue Tracker][issue-tracker] section for tips on finding issues.

## Introduction

Pytype is built around a "shadow bytecode interpreter", which traces through a
program's bytecode, mimicking the effects of the cpython interpreter but
tracking types rather than values.

A good starting point is to trace through the details of [pytype's main
loop][main-loop] and get a feel for how the bytecode interpreter works.

## Basic concepts

pytype's bytecode interpreter is referred to as the **Virtual Machine**, or VM.

As the VM traces a program, it builds up a **Typegraph**: a graph that maps the
flow of types through a program. Each **Node** in the typegraph roughly
correlates with a single statement in the program. A **Variable** tracks the
type information for a variable in the program being analyzed. A variable has
one or more **Bindings**, each associating it with a value at a particular node.
These associated values are known as **Abstract Values**, or sometimes **Data**
in the context of the typegraph, and represent types in the program.

A bytecode operation is modeled by popping variables from the VM's data stack,
manipulating them, and pushing the result back onto the stack. If an operation
cannot be completed legally, then pytype reports a type error. Throughout this
process, the VM queries the typegraph for what values a variable may be holding
at the current node.

Once the VM has finished execution, it converts the program's top-level
definitions into **PyTD** format, an AST representation that is easy to
serialize and deserialize, and writes the AST to a file. If a later invocation
of pytype analyzes a program that depends on this one, it will read the file and
convert the PyTD nodes back to abstract values for internal use.

## Updating the developer guide

When adding a new page, link to it from the GitHub
[landing page][dev-landing-page].

Add new images to the [images directory][images-dir]. Check in both an SVG and a
PNG, and embed the latter in docs for consistent rendering.

<!-- General references -->
[dev-landing-page]: https://github.com/google/pytype/blob/master/docs/_layouts/dev_guide.html
[issue-tracker]: process.md#issue-tracker
[images-dir]: https://github.com/google/pytype/blob/master/docs/images/
[main-loop]: main_loop.md
