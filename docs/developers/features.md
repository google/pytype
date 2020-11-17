# Supporting new typing features

<!--ts-->
   * [Supporting new typing features](#supporting-new-typing-features)
      * [1. Update typing.pytd.](#1-update-typingpytd)
      * [2. Update typing_overlay.](#2-update-typing_overlay)
         * [2a. Parameterized classes in abstract.py](#2a-parameterized-classes-in-abstractpy)
      * [3. Implement conversion between abstract and PyTD instances.](#3-implement-conversion-between-abstract-and-pytd-instances)
         * [3a. PrintVisitor](#3a-printvisitor)
      * [4. Implement abstract matching.](#4-implement-abstract-matching)

<!-- Added by: rechen, at: 2020-11-16T01:36-08:00 -->

<!--te-->

The standard library `typing` module regularly gains new features that we then
want to support in pytype. This doc describes the steps to add such support.

## 1. Update typing.pytd.

The first step is to declare the new feature in the type stub for `typing`,
located in `pytype/pytd/builtins`. This declaration should describe how the
feature is typed. See [Type Stubs][type_stubs] for more information.

Note:
Make sure to modify the `typing.pytd` file in all of the `2/`, `3/`, and
`2and3/` subdirectories!

For some simple features, this is enough! For example, all pytype does for
`typing.runtime_checkable` is pass the input through unchanged, so declaring it
as an identity function is the only step needed.

## 2. Update typing_overlay.

For more complicated features, we will also need an entry in
`pytype/overlays/typing_overlay.py` to control how the object behaves when
interacted with. See [Overlays][overlays] for more information.

Some common techniques that you'll see in `typing_overlay`:

* For methods: subclassing `abstract.PyTDFunction` and overriding `call()`. When
  a `PyTDFunction` is invoked, the arguments are passed to the `call` method,
  which should return the result of the invocation.
* For parameterizable classes: subclassing `TypingContainer` and overriding some
  of the behavior of `getitem_slot`. The `getitem_slot` method implements
  `__getitem__`; i.e., it controls what happens when the class is parameterized.
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
* For not-yet-implemented features: mapping the feature to `not_supported_yet`.

### 2a. Parameterized classes in abstract.py

Many of the parameteriz<i>able</i> classes in `typing_overlay.py` have a
corresponding parameteriz<i>ed</i> class in `abstract.py.` For example,
parameterizing `typing_overlay.Tuple` produces an `abstract.TupleClass`. If you
need a parameterized object to have special behavior - e.g., instantiating a
`TupleClass` will produce a heterogeneous `abstract.Tuple`, rather than a plain
homogeneous `Instance(tuple)` - you will need to add a parameterized class,
subclassing `abstract.ParameterizedClass`.

## 3. Implement conversion between abstract and PyTD instances.

TODO: write me!

### 3a. PrintVisitor

TODO: write me!

## 4. Implement abstract matching.

TODO: write me!

[_get_value_info-docstring]: https://github.com/google/pytype/blob/793623e2f8db70967b8e35a4411c6c6835a67c03/pytype/abstract.py#L1296-L1306

[overlays]: overlays.md
[type_stubs]: type_stubs.md
