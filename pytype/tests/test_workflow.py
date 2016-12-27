"""Test cases that match the examples in our documentation."""

import os
from pytype import utils
from pytype.tests import test_inference


class WorkflowTest(test_inference.InferenceTest):
  """Tests for examples extracted from our documentation."""


  def testWorkflow1(self):
    ty = self.Infer("""
      class ConfigParser(object):
        def __init__(self, filename):
          self.filename = filename
        def read(self):
          with open(self.filename, "r") as fi:
            return fi.read()

      cp = ConfigParser(__any_object__())
      cp.read()
      """, deep=False, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      cp = ...  # type: ConfigParser

      class ConfigParser(object):
        # TODO(pludemann): remove '-> NoneType'
        def __init__(self, filename: str or buffer or unicode) -> NoneType
        def read(self) -> str
        filename = ...  # type: str or buffer or unicode
    """)

  def testTutorial1(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def f(x: int, y: int) -> int:
        return "foo"
      """, deep=True)
    self.assertErrorLogIs(errors, [
        (3, "bad-return-type")
    ])

  def testTutorial2(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Any, Dict, List
      def keys(d: Dict[str, Any]) -> List[str]:
        return list(d.keys())

      keys({"foo": 3})
      """)

  def testTutorial3(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Optional

      def find_name_in_list(d: list, name: str) -> Optional[int]:
        try:
          return d.index(name)
        except ValueError:
          return None

      find_name_in_list(["foo", "bar"], "foo")
    """)

  def testTutorial4(self):
    _, errors = self.InferAndCheck("""\
      import socket
      class Server:
        def __init__(self, port):
         self.port = port

        def listen(self):
          self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.socket.bind((socket.gethostname(), self.port))
          self.socket.listen(backlog=5)

        def accept(self):
          return self.socket.accept()
    """)
    self.assertErrorLogIs(errors, [
        (12, "attribute-error")
    ])

  def testTutorial5(self):
    self.assertNoErrors("""\
      import socket
      class Server:
        def __init__(self, port):
         self.port = port

        def listen(self):
          self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.socket.bind((socket.gethostname(), self.port))
          self.socket.listen(backlog=5)

        def accept(self):
          return self.socket.accept()  # pytype: disable=attribute-error
    """)

  def testTutorial6(self):
    with utils.Tempdir() as d:
      d.create_file("ftp.pyi", """
        class Server:
          def start(self): ...
      """)
      self.assertNoErrors("""\
        from __future__ import google_type_annotations
        import ftp

        def start_ftp_server(server: ftp.Server):
          return server.start()
      """, pythonpath=[d.path])

  def testTutorial7(self):
    with utils.Tempdir() as d:
      d.create_file("ftp.pyi", """
        class Server:
          def start(self): ...
      """)
      self.assertNoErrors("""\
        from __future__ import google_type_annotations
        import typing

        if typing.TYPE_CHECKING:
          import ftp

        def start_ftp_server(server: ftp.Server):
            return server.start()
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_inference.main()
