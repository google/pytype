# Style Guide

<!--* freshness: { owner: 'rechen' reviewed: '2021-09-17' } *-->

This is a living document in which pytype coding best practices will be
documented.

* Avoid creating unnecessary variables. Creating too many variables bloats the
  typegraph and slows down analysis.
* Clearly distinguish between variables, bindings, and values. Instances of
  these classes are often passed around in similar contexts, so for readability,
  make sure instances are either named (e.g., `foo_var`) or annotated
  (`foo: cfg.Variable`) to make their types obvious.
* Use `abstract_utils.get_atomic_value` or
  `abstract_utils.get_atomic_python_constant` to unwrap variables that contain a
  single value, unless you have a specific reason not to. Other options, like
  `value = var.data[0]` or `value, = var.data`, silently discard data or produce
  unclear error messages.
