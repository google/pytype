# Copyright (c) 2016 Google Inc. (under http://www.apache.org/licenses/LICENSE-2.0)
class C(object):
    def f(self, x):
        pass

    def g(self):
        def f(x): #gets ignored by pytype but fixer sees it, generates warning (FIXME?)
            return 1
        return f
