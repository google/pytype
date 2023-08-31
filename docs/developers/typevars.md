# TypeVars

<!--* freshness: { exempt: true } *-->

**WARNING:** UNDER CONSTRUCTION

Pytype does the following to support class-scoped TypeVars in instance methods:

*   For InterpreterFunctions:
    *   Class.update_signature_scope() adds class scopes to TypeVars.
    *   abstract_utils.get_generic_type() builds generic annotations for `self`.
    *   annotation_utils extracts the names of class-scoped TypeVars from
        instances so that the TypeVars can be used in annotations in method
        bodies.
*   For PyTDFunction, the AdjustSelf visitor adds a generic type annotation to
    `self` when inside a function inside a class.
