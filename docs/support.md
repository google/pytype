# Support

This page lists the Python versions and features supported by the latest version
of pytype.

<!--ts-->
   * [Support](#support)
      * [Python Version](#python-version)
      * [Features](#features)
         * [Core](#core)
         * [Typing](#typing)
         * [Third-Party Libraries](#third-party-libraries)

<!-- Added by: rechen, at: 2021-01-08T12:38-08:00 -->

<!--te-->

## Python Version

*   **Analyzes**: Whether pytype can analyze code written for this version
*   **Runs In**: Whether pytype itself can run in this version
*   **Issue**: Tracking issue for dropping support (older versions) or adding it
    (upcoming versions), if applicable

Version | Analyzes | Runs In | Issue
:-----: | :------: | :-----: | :----------:
2.7     | ✅        | ❌       | [#545][py27]
3.5     | ✅        | ❌       | [#677][py35]
3.6     | ✅        | ✅       |
3.7     | ✅        | ✅       |
3.8     | ✅        | ✅       |
3.9     | ❌        | ❌       | [#749][py39]

## Features

*   **Supports**: ✅ (yes), ❌ (no), or 🟡 (partial)
*   **Issues**: Notable issue(s), if applicable

### Core

Note: pytype supports all language and stdlib features in its supported versions
unless noted otherwise. This section lists features that are difficult to type
for which pytype has or intends to add custom support.

Feature                                  | Supports | Issues
---------------------------------------- | :------: | :----------:
Control Flow Analysis ("Type Narrowing") | ✅        |
collections.namedtuple                   | ✅        |
Dataclasses                              | ✅        |
Enums                                    | 🟡        | [#788][enum]

### Typing

Feature                                                  | Supports | Issues
-------------------------------------------------------- | :------: | :----:
PEP 484 -- Type Hints                                    | ✅        |
PEP 526 -- Syntax for Variable Annotations               | ✅        |
PEP 544 -- Protocols                                     | 🟡        | [#524][protocol-attributes], [#789][protocol-modules], [#792][protocol-generic]
PEP 561 -- Distributing and Packaging Type Information   | ❌        | [#151][packaging]
PEP 563 -- Postponed Evaluation of Annotations           | ✅        |
PEP 585 -- Type Hinting Generics in Standard Collections | ✅        |
PEP 586 -- Literal Types                                 | 🟡        | [#790][literal-enums]
PEP 589 -- TypedDict                                     | ❌        | [#680][typeddict]
PEP 591 -- Adding a Final Qualifier to Typing            | ❌        | [#680][final]
PEP 593 -- Flexible Function and Variable Annotations    | ❌        | [#791][annotated]
PEP 604 -- Allow Writing Union Types as X \| Y           | ❌        | [#785][union-pipe]
PEP 612 -- Parameter Specification Variables             | ❌        | [#786][param-spec]
PEP 613 -- Explicit Type Aliases                         | ❌        | [#787][typealias]
Custom Recursive Types                                   | ❌        | [#407][recursive-types]
Generic Type Aliases                                     | 🟡        | [#793][generic-aliases]
Type Annotation Inheritance                              | ❌        | [#81][annotation-inheritance]

### Third-Party Libraries

Note: This section does not list all third-party libraries that pytype supports,
only the ones that are difficult to type for which pytype has or intends to add
custom support.

Feature    | Supports | Issues
---------- | :------: | :----------------------:
Attrs      | ✅        |
Flax       | 🟡        | Google-internal
Numpy      | 🟡        | Minimal type stub
Tensorflow | 🟡        | Minimal, Google-internal

[annotated]: https://github.com/google/pytype/issues/791
[annotation-inheritance]: https://github.com/google/pytype/issues/81
[enum]: https://github.com/google/pytype/issues/788
[final]: https://github.com/google/pytype/issues/680
[generic-aliases]: https://github.com/google/pytype/issues/793
[literal-enums]: https://github.com/google/pytype/issues/790
[packaging]: https://github.com/google/pytype/issues/151
[param-spec]: https://github.com/google/pytype/issues/786
[protocol-attributes]: https://github.com/google/pytype/issues/524
[protocol-generic]: https://github.com/google/pytype/issues/792
[protocol-modules]: https://github.com/google/pytype/issues/789
[py27]: https://github.com/google/pytype/issues/545
[py35]: https://github.com/google/pytype/issues/677
[py39]: https://github.com/google/pytype/issues/749
[recursive-types]: https://github.com/google/pytype/issues/407
[typealias]: https://github.com/google/pytype/issues/787
[typeddict]: https://github.com/google/pytype/issues/680
[union-pipe]: https://github.com/google/pytype/issues/785
