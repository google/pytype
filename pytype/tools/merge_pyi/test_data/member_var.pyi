# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
class C(object):
    y = ...  # type: Union[complex, float, int, long]

    def __init__(self, x: Union[complex, float, int, long]) -> None: ...
