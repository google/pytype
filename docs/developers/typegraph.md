# The Typegraph

<!--*
freshness: { owner: 'tsudol' reviewed: '2020-11-20' }
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
      * [The Solver Algorithm](#the-solver-algorithm)
         * [A Simple Example](#a-simple-example)
         * [A More Complex Example](#a-more-complex-example)
         * [Shortcircuiting and the solver cache](#shortcircuiting-and-the-solver-cache)

<!-- Added by: tsudol, at: 2020-11-20T10:48-08:00 -->

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

## The Solver Algorithm

This section is intended as a starting point to help you understand what the
solver is doing. The code itself is somewhat complex, but the comments, this
guide and the solver tests should clarify it.

### A Simple Example

Let's start with a simple example. The CFG is just three nodes:

```
n0 -> n1 -> n2
```

There are also two bindings. For clarity, they're named after the variable and
value that they bind together.

1.  Binding `x=5`: `x = 5` at `n0`.
2.  Binding `y=7`: `y = x + 2` at `n1`.

A query for this very simple CFG would be, for example, "is `y = x + 2` visible
at n2?" For this query, the list of _goals_ is `[y=7]`, and the _start node_ is
`n2`. The tuple of the list of goals and the start node forms the state of the
solver: `([y=7], n2)` is the initial state for this query.

To answer this, the solver starts at `n2`. There are no relevant bindings here,
so no goals are resolved. It then checks which node it should move to next.
Since `y=7` is bound at `n1,` and `n1` can be reached moving backwards from
`n2`, the solver chooses to move to `n1`. The new solver state is `([y=7], n1)`.

At `n1`, the solver finds binding `y=7`. This fulfills a goal! It removes `y=7`
from the goal list, then checks `y=7`'s source set for new goals. The source set
of a binding is the list of bindings that are used to construct a new binding.
The value bound to `y` is `x + 2`, which contains the binding `x=5`, so that
binding is in the source set of `y=7`. It then looks for a new node to move to,
same as before. In this case, it's looking for the origin node for `x=5`, which
is `n0`. Since there's a path between `n0` and `n1`, the new state is `([x=5],
n0)`.

Finally, at `n0`, the solver finds `x=5`. That goal is satisfied and therefore
removed from the goal set. Since `x=5` has no bindings in its source set, the
solver stops here -- the query has been solved and the solver can answer `true`.

### A More Complex Example

Let's consider a more complex example with more CFG features. Consider this
sample program:

```
a = 1          x0
b = 2          | \
c = True       |  \
if c:          x1 |
  d = a + 2    |  |
else:          |  x2
  d = a + b    | /
e = d + a      x3
```

In this example, there are 6 bindings (`a=1`, `b=2`, `c=True`, `d=a2`, `d=ab`,
`e=da`) across four nodes. Additionally, `x1` and `x2` both have conditions,
which are the bindings `c=True` and `c=False`.

The example query will be: "Is `e = d + a` visible from `x3`?"

State 1: `([e=da], x3)`. The goal is immediately fulfilled. But the binding has
two possible constructions: `d=a2 + a=1` or `d=ab + a=1`. The solver now has
multiple states to consider: `([d=ab, a=1], x2)` and `([d=a2, a=1], x1)`.

State 2.1: `([d=ab, a=1], x2)`. This node fulfills the first goal, creating a
new goal set of `([b=2, a=1])`. Also, `x2` has the condition `c=False`, so
that's added to the goal set. All three bindings have the same origin of `x0`,
so that's the next node to visit: `([b=2, a=1, c=False], x0)`.

State 2.2: `([b=2, a=1, c=False], x0)`. This node fulfills `a=1` and `b=2`,
leaving just `c=False`. Since that binding has no source set, there are no more
nodes to consider, and the solver returns false for this branch.

State 3.1: `([d=a2, a=1]), x1)`. The goal `d=a2` is fulfilled, and its source
set (just `a=1`, since `2` is a constant) is checked for new goals. Since `a=1`
is already a goal, the goal set doesn't change. The node condition (`c=True`) is
also added to the goal set. The new state is `([a=1, c=True], x0)`.

State 3.2: `([a=1, c=True], x0)`. At this node, the solver finds both goals are
fulfilled. Since neither one has a source set, the solver finds no new goals,
which means this branch succeeds.

The queries can get more complex from here. One case to consider: it's possible
to construct a goal set like `([d=a2, d=ab])`. The solver will detect this
contradiction -- there's no way to satisfy two different bindings on one
variable -- and reject the state.

### Shortcircuiting and the solver cache

The solver employs two small optimizations for speading up queries.

The first trick is _shortcircuiting_. Queries with multiple bindings take longer
to evaluate, so the solver first checks if the query is at all possible by
breaking the initial goals into their own, individual queries.

Consider the CFG used in the previous example. A query like `([d=a2, ...], x2)`
will fail because there's no path from `x2` to where `d=a2` is bound in `x1`. Or,
similarly, `([c=False, ...], x3)`, which will fail because `c` is only bound to
`True` in the CFG. Larger queries with these bindings at these nodes will always
fail, so the solver saves time by shortcircuiting them.

Note that shortcircuiting only stops queries that are easily contradicted in this
way. More complex queries that fail due to the interplay between bindings --
such as `([d=ab, d=a2], x3)` -- will not be shortcircuited.

In addition, each state the solver encounters is cached, including all the
states created during shortcircuiting, with the solution that was found. Note
that the cache does not persist between solver instances, so it is only useful
if a solver is queried multiple times. It is also helpful for preventing
infinite recursion; new states are considered to be solvable, on the reasoning
that if the state _couldn't_ be solved in an ensuing state then the cache entry
would be updated.
