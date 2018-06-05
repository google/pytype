# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
# pytype generates member variable annotations as comments, check that fix_annotate ignores them
# properly

class C(object):
    def __init__(self, x):
        self.y = 1 + x
