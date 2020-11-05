# The Typegraph

<!--*
freshness: { owner: 'tsudol' reviewed: '2020-11-02' }
*-->

<!--ts-->
   * [The Typegraph](#the-typegraph)
      * [Introduction](#introduction)
      * [Binding Data](#binding-data)
      * [Program](#program)
         * [Default Data](#default-data)
      * [Sets in the Typegraph](#sets-in-the-typegraph)
         * [std::set or std::unordered_set?](#stdset-or-stdunordered_set)
      * [Reachability](#reachability)
         * [Implementation](#implementation)

<!-- Added by: rechen, at: 2020-11-05T09:16-08:00 -->

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

## Program

The main purpose of the `Program` is to organize the CFG. Almost all of its
functionality is devoted to creating `CFGNode`s, `Variable`s and `Binding`s. It
also holds the Solver that queries the CFG. Only one `Program` is alive at any
time, except during tests. While `Program` and the typegraph as a whole are
designed to be thread-safe, the rest of pytype is not guaranteed to be.

The advantage of having the `Program` maintain ownership of all CFG objects is
we can guarantee that all parts of the CFG will stay alive as long as the
`Program` is alive. It provides a single, centralized location for accessing and
modifying the CFG and the solver.

### Default Data

Sometimes a `Binding` needs to be created without any particular data to be
stored in it. By default, the `Program` will fill in the `Binding` with a
`nullptr`, which is a sane enough default for C++ code. But pytype expects
`Binding`s to contain valid data, and since `Binding`s are immutable, it's
useful for the `Program` to allow the default `Binding` data to be set to a more
meaningful value.

That said, the default data is rarely used, because `Binding`s are almost always
created with particular data in mind. In fact, a `Binding` is only created
without specific data when pytype hits a complexity limit. In particular,
default data is used when:

1.  there are too many possible variable combinations, as seen in
    [`abstract_utils.get_views()`][get_views]
2.  there are too many `Binding`s on one `Variable`, as seen in
    [`Variable.FindOrAddBinding()`][find_or_add_binding]

In both cases, default data ensures the `Binding`s have valid data, allowing
pytype to continue analysis in the face of complexity.

Pytype sets the default data to `abstract.Unsolvable`.

[find_or_add_binding]: https://github.com/google/pytype/blob/master/pytype/typegraph/typegraph.cc#L238
[get_views]: https://github.com/google/pytype/blob/master/pytype/abstract_utils.py#L124

## Sets in the Typegraph

The typegraph makes good use of sets to keep track of things like which nodes
are blocked by some condition, or the set of `Binding`s that form the source set
of another `Binding`. The sets are implemented by giving each `CFGNode` and
`Binding` an ID (which are unique between objects of the same type, but not
globally unique) and ordering them by their ID by overloading `<`. There is also
a helper function, `pointer_less`, which compares pointers by dereferencing
them. Hence, `CFGNodeSet` is defined as `std::set<const CFGNode*,
pointer_less<CFGNode>`, and similarly for `SourceSet`.

Originally, these sets did not use `pointer_less` and just compared the
pointers. This is undefined behavior.

### std::set or std::unordered_set?

The typegraph uses `std::set` to increase determinism: any source of
nondeterminism or randomness in pytype has a chance to leak into the pickled
type stub files, which is problematic. Additionally, the typegraph does not and
cannot guarantee that the items in a set won't be modified, which violates the
`std::unordered_set` invariants. Finally, iterating over and comparing sets is
more efficient for `std::set`.

## Reachability

A basic operation when analyzing the CFG is checking if there is a path between
two nodes. This is used when checking if a binding's origin is visible at a
given node, for example. Queries always progress from a child node to the
parent, in the opposite direction of the edges of the CFG. To make these lookups
faster, the `Program` class uses a **backwards reachability** cache that's
handled by the `ReachabilityAnalyzer` class. Backwards reachability means that
the reachability analysis proceeds from child to parent, in the opposite
direction of the directed edges of the graph.

The `ReachabilityAnalyzer` tracks the list of adjacent nodes for each CFG node.
For node `i`, `reachable[i][j]` indicates whether `j` is reachable from `i`.
When an edge is added to the reachability cache, the cache updates every node to
see if connections are possible.

For example, consider three nodes `A -> B -> C`. The cache would be initialised
as:

```
reachable[A] = [True, False, False]
reachable[B] = [False, True, False]
reacahble[C] = [False, False, True]
```

(A node can always be reached from itself.) Since there's a connection from `B`
to `C`, the backwards edge `C -> B` is added to the cache:

```
reachable[A] = [True, False, False]
reachable[B] = [False, True, False]
reacahble[C] = [False, True, True]
```

Then the backwards edge `B -> A` is added:

```
reachable[A] = [True, False, False]
reachable[B] = [True, True, False]
reacahble[C] = [True, True, True]
```

The cache now shows that `A` can only reach itself, `B` can reach itself and
`A`, and `C` can reach all three nodes.

### Implementation

Every CFG node has an ID number of type `size_t`, which these docs will assume
is 64 bits. A naive implementation would make `reachable[n]` a list of the IDs
of the nodes reachable from node `n`, but at 8 bytes per node and potentially
thousands of nodes, that will get too expensive quickly. Instead, nodes are
split into _buckets_ based on their ID. Each bucket tracks 64 nodes, so the top
58 bits of the ID determine the node's bucket and the bottom 6 bits determine
the node's index within the bucket.

These buckets are implemented using bit vectors. Since a bucket covers 64 nodes,
it's represented by an `int64_t`. A node's reachable list is then a
`std::vector<int64_t>`, and the reachability cache that tracks every node's
reachable list is a `std::vector<std::vector<int64_t>>`. All together, node `j`
is reachable from node `i` if `reachable[i][bucket(j)] & bit(j) == 1`.

For example, consider a CFG with 100 nodes, which have IDs from 0 to 99. There
will be 100 entries in the reachability cache, one for each node, such that
`reachable[n]` corresponds to the nodes that are backwards reachable from node
`n`. `reachable[n]` is a `std::vector<int64_t>` with two elements, the first
tracking nodes 0 - 63 and the second tracking nodes 64 - 99, with room to track
another 28 nodes.

Let's check if node 75 is backwards reachable from node 30: `is_reachable(30,
75)`.

1.  Find node 75's bucket: `bucket = 75 >> 6 = 1`. (This is equivalent to `75 /
    64`.)
1.  Find node 75's bit: `bit = 1 << (75 & 0x3F) = 1 << 11`.
1.  Check node 30's reachability: `reachable[30][bucket] & bit`.

Adding a new node to the reachability cache is accomplished by adding another
entry to `reachable`. There is a catch: the cache must check if a new bucket is
needed to track the new node. If one is, then every node's reachable list is
extended with one more bucket. Finally, `reachable[n][bucket(n)] = bit[n]` is
set, indicating that node `n` is reachable from itself.

Adding an edge between two nodes is only slightly more complex. Because the
cache tracks reachability, adding an edge may update every node. Remember the `A
-> B -> C` example previously: `add_edge(B, A)` updated both `B` and `C`,
because `B` is reachable from `C`. For `add_edge(src, dst)`, the cache checks if
`src` is reachable from each node `i`, and if so, bitwise-ORs `reachable[i]` and
`reachable[dst]` together. Because `src` is reachable from itself, this will
also update `reachable[src]` when `i == src`.

<!--

Hashing and Sets

-   CFGNodes and Bindings have partial ordering using operator<
-   They also have Hashes
-   This + everything in map_util.h is just to enable using sets and hashes of
    CFGnodes, bindings, etc.

Solver

-   The algorithm used.
-->
