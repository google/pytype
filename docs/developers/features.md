# Supporting new typing features

<!--ts-->
   * [Supporting new typing features](#supporting-new-typing-features)
      * [Introduction](#introduction)
      * [Loading](#loading)
         * [Type stub parsing](#type-stub-parsing)
         * [Conversion from a PyTD node to an abstract value](#conversion-from-a-pytd-node-to-an-abstract-value)
      * [Analysis](#analysis)
         * [typing_overlay](#typing_overlay)
         * [Parameterized classes](#parameterized-classes)
         * [typing_extensions_overlay](#typing_extensions_overlay)
         * [Matching](#matching)
      * [Output](#output)
         * [Conversion from an abstract value to a PyTD node](#conversion-from-an-abstract-value-to-a-pytd-node)
         * [PrintVisitor](#printvisitor)
      * [Partial support](#partial-support)

<!-- Added by: rechen, at: 2020-11-23T14:36-08:00 -->

<!--te-->

## Introduction

The standard library `typing` module regularly gains new features that we then
want to support in pytype. Support needs to be added in the loading, analysis,
and output phases of pytype's execution.

## Loading

To allow the feature to be imported in source files and referenced in type 
stubs, we need to declare it in the stub for `typing`, located in
`pytype/pytd/builtins`. This declaration should describe
[how the feature is typed][type_stubs].

Note:
Make sure to modify the `typing.pytd` file in all of the `2/`, `3/`, and
`2and3/` subdirectories!

For sufficiently simple features, adding this declaration is the only thing you
need to do! For example, all pytype does for `typing.runtime_checkable` is pass
the input through unchanged, so it can just be declared as an identity function.

### Type stub parsing

Some features require a new [node type][pytd] in the AST representation of type
stubs. For example, `typing.Tuple` required the addition of a `pytd.TupleType`
node to distinguish between heterogeneous and homogeneous tuples. When you add a
new node type, you also need to teach the [stub parser][parser] to construct
instances of it.

### Conversion from a PyTD node to an abstract value

If you've defined a new PyTD node type or a new abstract class (see
[below][parameterized-classes]) for your feature, you should specify how nodes
are to be [converted][abstract-converter] to abstract values.

## Analysis

### typing_overlay

Complicated features often need an entry in `pytype/overlays/typing_overlay.py`
to [control][overlays] how the object behaves when interacted with.

Common techniques that you'll see in `typing_overlay`:

* For methods: subclassing `abstract.PyTDFunction` and overriding `call()`. When
  a `PyTDFunction` is invoked, the arguments are passed to the `call` method,
  which should return the result of the invocation.
* For parameterizable classes: subclassing `typing_overlay.TypingContainer` and
  overriding some of the behavior of `getitem_slot`. The `getitem_slot` method
  implements `__getitem__`; i.e., it controls what happens when the class is
  parameterized.
  * The easiest approach is to override the `_get_value_info` helper method.
    This method is passed the parameter values and returns info on what the
    parameterized object should look like (see the
    [docstring][_get_value_info-docstring]) that another helper, `_build_value`,
    will use to construct the object.
  * If you need more control, you can override the `_build_inner` and
    `_build_value` methods that are directly called by `_getitem_slot`.
    `_build_inner` takes the raw parameter variables and extracts the values,
    which are passed to `_build_value`. `_build_value` constructs the
    parameterized object.
  * For complete control, override `getitem_slot`. This method takes a slice
    variable containing the parameter variables and returns the parameterized
    object.

### Parameterized classes

Many of the parameteriz<i>able</i> classes in `typing_overlay.py` have a
corresponding parameteriz<i>ed</i> class in `abstract.py.` For example,
parameterizing `typing_overlay.Tuple` produces an `abstract.TupleClass`. If you
need a parameterized object to have special behavior - e.g., instantiating a
`TupleClass` will produce a heterogeneous `abstract.Tuple`, rather than a plain
homogeneous `Instance(tuple)` - you will need to add a parameterized class,
subclassing `abstract.ParameterizedClass`.

### typing_extensions_overlay

If you implement a feature that is not available in all Python versions that
pytype supports, it can be backported to earlier versions by adding it to the
third-party `typing_extensions` module. For example, `typing.Literal` is new in
Python 3.8, so we support referring to it as `typing_extensions.Literal` in 3.7
and below. To backport a feature, simply make `typing_extensions.{FeatureName}`
an alias to `typing.{FeatureName}`:

* For features that do not have an entry in `typing_overlay`, you can do this by
  lookup via the abstract converter ([example][typing_extensions.Protocol]).
* For features in the overlay, you should instead copy over the overlay member
  ([example][typing_extensions.Literal]).

### Matching

Arguably the most critical piece of supporting a new feature is defining its
[matching][matcher] behavior, as a value being matched against an annotation and
vice versa. For example, for `typing.Tuple`, we had to define rules for both
this case:

```python
def f(x: X): ...
f((a1, ..., a_n))  # what types X should this tuple match?
```

and this one:

```python
def f(x: Tuple[A1, ..., A_n]): ...
f(x)  # what values x should match this tuple?
```

If your feature is a class, you should modify the matcher method
`_match_type_against_type`; otherwise, you likely need to go one level up and
change `_match_value_against_type`. Roughly speaking, these methods are
structured as a series of `isinstance` checks on the value and the annotation. A
good starting point is to figure out which `isinstance` check(s) the feature can
satisfy, then determine whether the value and annotation types described by the
check can match each other. If so, you'll need to update the `subst` dictionary
with substitutions for any type parameters involved in the match and return
`subst`; else, return `None`.

Important: if you directly modify the substitution dictionary, make a copy of it
first! The same dictionary may be the input to multiple matches using the same
type parameters.

## Output

### Conversion from an abstract value to a PyTD node

If you've defined a new PyTD node type or a new abstract class for your feature,
you'll likely need to modify the [PyTD converter][pytd-converter] to ensure that
the right AST is produced for a module's inferred types. Similar to the matcher,
the converter operates via a series of `isinstance` checks on abstract classes,
so you will need to add an `isinstance` check for your new class and/or modify
the body of a check to return your new node.

### PrintVisitor

Lastly, you may need to modify how
[pytd_visitors.PrintVisitor][pytd_visitors.PrintVisitor] stringifies nodes of
the new feature.

## Partial support

It is often desirable to check in partial support for a complicated feature and
finish it later. Some tips for doing this gracefully:

* To prevent premature use, map a feature to `typing_overlay.not_supported_yet`
  to generate an error when it is imported in source files.
* If you've implemented only the PyTD logic for a feature, convert the pytd
  nodes to `vm.convert.unsolvable` to treat them as `Any` in abstract analysis.
* If you've implemented only the abstract logic for a feature, convert the
  abstract values to `pytd.AnythingType` to produce `Any` in the inferred stub.

[_get_value_info-docstring]: https://github.com/google/pytype/blob/793623e2f8db70967b8e35a4411c6c6835a67c03/pytype/abstract.py#L1296-L1306

[abstract-converter]: abstract_values.md#construction
[matcher]: abstract_values.md#matching
[overlays]: overlays.md
[parameterized-classes]: #parameterized-classes
[parser]: type_stubs.md#parser

[pytd]: https://github.com/google/pytype/blob/master/pytype/pytd/pytd.py

[pytd-converter]: type_stubs.md#stub-generation

[pytd_visitors.PrintVisitor]: https://github.com/google/pytype/blob/ffc6aab636329075ee2d9cd443e83d0f790a9b4c/pytype/pytd/pytd_visitors.py#L269

[type_stubs]: type_stubs.md

[typing_extensions.Literal]: https://github.com/google/pytype/blob/ffc6aab636329075ee2d9cd443e83d0f790a9b4c/pytype/overlays/typing_extensions_overlay.py#L11

[typing_extensions.Protocol]: https://github.com/google/pytype/blob/ffc6aab636329075ee2d9cd443e83d0f790a9b4c/pytype/overlays/typing_extensions_overlay.py#L43
