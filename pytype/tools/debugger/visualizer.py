"""Library for creating visualizations of the pytype typegraph.

This is intended as a convenient wrapper for the jinja2 template. All it does is
load the template, encode the program, then call template.render.

Because the visualizer template uses an `include` statement, a full
jinja2.Environment needs to be created. generate() accepts a jinja2.Loader in
order to support different execution environments.
"""

import jinja2
from pytype.typegraph import cfg
from pytype.typegraph import typegraph_serializer

_TEMPLATE_NAME = "visualizer.html.jinja2"

# If it's good enough for google.com, it's good enough for us.
_CYTOSCAPE_URL = "https://www.gstatic.com/external_hosted/cytoscape/cytoscape.js"
_DAGRE_URL = "https://www.gstatic.com/external_hosted/dagre/dagre.js"
_CYTOSCAPE_DAGRE_URL = "https://www.gstatic.com/external_hosted/cytoscape-dagre/cytoscape-dagre.js"


def generate(
    program: cfg.Program,
    var_table: dict[int, str],
    loader: jinja2.BaseLoader,
    cytoscape_url: str = _CYTOSCAPE_URL,
    dagre_url: str = _DAGRE_URL,
    cytoscape_dagre_url: str = _CYTOSCAPE_DAGRE_URL,
) -> str:
  """Generate the visualization webpage.

  Args:
    program: cfg.Program. The instance of the program to visualize.
    var_table: dict[int, str]. A mapping of cfg.Variable IDs to names.
    loader: jinja2.BaseLoader. The loader needs to be able to load files in this
      file's directory.
    cytoscape_url: str. The location of the Cytoscape library. May be a URL or
      a path.
    dagre_url: str. The location of the Dagre library. May be a URL or a path.
    cytoscape_dagre_url: str. The location of the cytoscape-dagre library. May
      be a URL or a path.

  Returns:
    str. The rendered visualization page.
  """
  env = jinja2.Environment(loader=loader)
  template = env.get_template(_TEMPLATE_NAME)
  return template.render(
      cytoscape_url=cytoscape_url,
      dagre_url=dagre_url,
      cytoscape_dagre_url=cytoscape_dagre_url,
      program=typegraph_serializer.encode_program(program),
      var_table=var_table,
  )
