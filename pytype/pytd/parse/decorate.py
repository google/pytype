# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-

# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO(kramm): This is experimental.

"""Allows "decorating" the classes of a nested tree.

Allows changing classes in a tree to ones with more functionality, by returning
a new tree with nodes that were reconstructed using the newer class.

Usage:

  # "decorate" is, essentially, a map that collects all classes it decorates.
  # Needed since we don't want different decorators conflicting.
  decorate = Decorator()

  @decorate
  class ClassType(pytd.ClassType):
    def Print(self):
      ...

  @decorate
  class NamedType(pytd.NamedType):
    def Print(self):
      ...

  node = decorate.Visit(node)
"""


from pytype.pytd.parse import visitors


class Decorator(object):
  """A class decorator to collect node replacements."""

  def __init__(self):
    self._mapping = {}

  def __call__(self, cls):
    """'Decorate' a given class. Only stores it for later."""
    self._mapping[cls.__name__] = cls
    return cls

  def Visit(self, node):
    """Replace a tree of nodes with nodes registered as replacements.

    This will walk the tree and replace each class with a class of the same
    name previously registered by using this class as a class decorator.

    Args:
      node: A pytd node.

    Returns:
      A new tree, with given nodes taken over by their replacement classes.
    """
    mapping = self._mapping

    # Build a visitor that performs the old_class -> new_class mapping:
    class Visitor(visitors.Visitor):
      visits_all_node_types = True
      name_to_class = mapping
      for name, new_cls in mapping.iteritems():

        def Visit(self, node):
          # Python doesn't allow us to build this as a closure, so we have to
          # use the clunky way of retrieving the replacement class.
          cls = self.name_to_class.get(node.__class__.__name__)
          if cls is not None:
            return cls(*node)
          else:
            return node
        locals()["Visit" + name] = Visit
    return node.Visit(Visitor())
