<!--* freshness: { exempt: true } *-->

# Pragmas

**Pragmas** are an experimental pytype feature, allowing programs to add
directives to the typechecker that provide additional information about sections
of code. Similarly to disables, they are implemented as python comments at the
end of a line, and are associated with that line of code.

For example, the following code:

```python
def f(x: int) -> str:  # pytype: pragma=cache-return
```

will associate a `cache-return` pragma with the function definition.

Pragmas are currently not considered a stable end-user feature; they are intended
to be used as a last resort in specific cases, for complex performance or
analysis issues that cannot be solved by more general heuristics. Reach out to
the pytype team if you have any questions or advanced use cases you think a
pragma would help with.

<!--ts-->
* [Pragmas](#pragmas)
   * [cache-return](#cache-return)

<!-- Created by https://github.com/ekalinin/github-markdown-toc -->
<!-- Added by: jankuehle, at: Wed Sep 11 11:06:46 AM UTC 2024 -->

<!--te-->

## cache-return

The `cache-return` pragma indicates that a function or method has no type-level
side effects or dependence on inputs, and can cache its return type without
symbolic execution at every call site.

This is a performance optimization, and needs to be used with great care, since
python code is often path-dependent. Pytype typically executes a function body
once for every combination of input types, since a call's return type can depend
on the types of its arguments. For methods, the body must also be executed for
each instance the method is called on, because a method call may modify
attributes on `self`. Therefore, forcing the use of a cached return type could
have correctness issues.
