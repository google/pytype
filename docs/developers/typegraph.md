# The Typegraph

<!--ts-->
   * [The Typegraph](#the-typegraph)
      * [Introduction](#introduction)
      * [Binding Data](#binding-data)

<!-- Added by: tsudol, at: 2020-08-28T16:29-07:00 -->

<!--te-->

## Introduction

This document explains some of the grittier details of pytype's typegraph. For
an overview of the typegraph, see the [CFG section][cfg-doc]. Because it is a
significant part of the hottest paths in pytype, the typegraph has a variety of
optimizations and caching to improve performance.

[cfg-doc]: ./index.md#cfg

## Binding Data

What data does a Binding actually bind?

In an expression like `x = a()`, pytype will add a Binding to `x` stating that
`x` is bound to whatever value `a` returns. This value will be an instance of (a
subclass of) `abstract.AtomicAbstractValue`, the type that represents values in
the Python program being analyzed.

But the typegraph is implemented in C++. That means the typegraph works with
`PyObject` pointers. And to store those, the Binding class can hold onto a
`void` pointer:

```c++
class Binding {
  ...
private:
  void* data;
};
```

In `cfg.cc`, adding data turns a `PyObject*` into a `void*`, and pulling data
out of a binding casts the `void*` back into a `PyObject*`. Simple enough!

But there's a subtle bug here. Python objects are tracked by a reference
counting garbage collector, and when nothing has a reference to a `PyObject`,
that `PyObject` will be cleaned up. It's easy to ensure the Binding increments
the reference count when data is added, of course. Conversely, it must be
ensured that if the Binding is cleaned up, the reference count is decremented.
As an additional twist, a single `PyObject*` may be held by multiple Bindings,
possibly across multiple Programs.

The solution is `BindingData`. Instead of a `void*`, a Binding holds a
[`std::shared_ptr`][shared-ptr-doc] to a `DataType`:

```c++
class DataType;  // A fictional opaque type for data that's added to Bindings.
typedef std::shared_ptr<DataType> BindingData;
...
class Binding {
  ...
private:
  BindingData data;
};
```

When a `PyObject*` value is added to a Binding, it's transformed into a
`BindingData` pointer with a cleanup function that decrements the reference
count. This approach ensures that each `PyObject*` has a correct reference
count, that no data objects will be deleted before the Binding is cleaned up,
and that deleting a Binding (or a whole Program) will correctly decrememnt the
reference count. This avoids potential memory leaks caused by `PyObject`s not
being cleaned up.

NOTE: Why use `DataType` instead of `PyObject`? This decouples the typegraph
implementation from Python, which is a cleaner design and makes testing easier.
Regular C++ values can be used for testing instead of having to construct
`PyObject`s.

[shared-ptr-doc]: https://en.cppreference.com/w/cpp/memory/shared_ptr

<!--
Program

-   default data
-   exists as a container for CFG (nodes, vars, bindings) and the Solver that
    acts upon it.

Reachability (reachable.h and .cc)

-   we know it's to make parts of the solver faster.
-   But how
-   and does it actually?

Hashing and Sets

-   CFGNodes and Bindings have partial ordering using operator<
-   They also have Hashes
-   This + everything in map_util.h is just to enable using sets and hashes of
    CFGnodes, bindings, etc.

Solver

-   The algorithm used.
-->
