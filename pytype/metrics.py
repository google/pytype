"""Classes for instrumenting code to collect various metrics.

Instrumentation consists of creating the metric and then updating it.
Creation can be performed at the module level or as a class attribute.  Since
the metric namespace is global, metrics should not be created by instances
unless that instance is certain to be a singleton.

Sample code:

_my_counter = metrics.Counter("my-counter")


def foo():
  _my_counter.inc()  # calls to foo() count as 1 unit.


def bar(n):
  _my_counter.inc(n)  # calls to bar() count as n units.
"""

import math
import re


# TODO(dbaum): Investigate mechanisms to ensure that counter variable names
# match metric names.

_METRIC_NAME_RE = re.compile(r"^[a-zA-Z_]\w+$")

_registered_metrics = {}  # Map from metric name to Metric object.
_enabled = False  # True iff metrics should be collected.


def _prepare_for_test(enabled=True):
  """Setup metrics collection for a test."""
  _registered_metrics.clear()
  global _enabled
  _enabled = enabled


def _get_report():
  """Return a string listing all metrics, one per line."""
  lines = [str(_registered_metrics[n]) + "\n"
           for n in sorted(_registered_metrics)]
  return "".join(lines)


class Metric(object):
  """Abstract base class for metrics."""

  def __init__(self, name):
    """Initialize the metric and register it under the specified name."""
    if _METRIC_NAME_RE.match(name) is None:
      raise ValueError("Illegal metric name: %s" % name)
    if name in _registered_metrics:
      raise ValueError("Metric %s has already been defined." % name)
    self._name = name
    _registered_metrics[name] = self

  @property
  def name(self):
    return self._name

  def _summary(self):
    """Return a string sumamrizing the value of the metric."""
    raise NotImplementedError

  def __str__(self):
    return "%s: %s" % (self._name, self._summary())


class Counter(Metric):
  """A monotonically increasing metric."""

  def __init__(self, name):
    super(Counter, self).__init__(name)
    self._total = 0

  def inc(self, count=1):
    """Increment the metric by the specified amount."""
    if count < 0:
      raise ValueError("Counter must be monotonically increasing.")
    if not _enabled:
      return
    self._total += count

  def _summary(self):
    return str(self._total)


class MapCounter(Metric):
  """A set of related counters keyed by an arbitrary string."""

  def __init__(self, name):
    super(MapCounter, self).__init__(name)
    self._counts = {}
    self._total = 0

  def inc(self, key, count=1):
    """Increment the metric by the specified amount.

    Args:
      key: A string to be used as the key.
      count: The amount to increment by (non-negative integer).

    Raises:
      ValueError: if the count is less than 0.
    """
    if count < 0:
      raise ValueError("Counter must be monotonically increasing.")
    if not _enabled:
      return
    self._counts[key] = self._counts.get(key, 0) + count
    self._total += count

  def _summary(self):
    details = ", ".join(["%s=%d" % (k, self._counts[k])
                         for k in sorted(self._counts)])
    return "%d {%s}" % (self._total, details)


class Distribution(Metric):
  """A metric to track simple statistics from a distribution of values."""

  def __init__(self, name):
    super(Distribution, self).__init__(name)
    self._count = 0  # Number of values.
    self._total = 0.0  # Sum of the values.
    self._squared = 0.0  # Sum of the squares of the values.
    self._min = None
    self._max = None

  def add(self, value):
    """Add a value to the distribution."""
    if not _enabled:
      return
    self._count += 1
    self._total += value
    self._squared += value * value
    if self._min is None:
      # First add, this value is the min and max
      self._min = self._max = value
    else:
      self._min = min(self._min, value)
      self._max = max(self._max, value)

  def _mean(self):
    if self._count:
      return self._total / float(self._count)

  def _stdev(self):
    if self._count:
      variance = ((self._squared * self._count - self._total * self._total) /
                  (self._count * self._count))
      if variance < 0.0:
        # This can only happen as the result of rounding error when the actual
        # variance is very, very close to 0.  Assume it is 0.
        return 0.0
      return  math.sqrt(variance)

  def _summary(self):
    return "total=%s, count=%d, min=%s, max=%s, mean=%s, stdev=%s" % (
        self._total, self._count, self._min, self._max, self._mean(),
        self._stdev())


class MetricsContext(object):
  """A context manager that configures and writes a metrics report."""

  def __init__(self, output_path):
    """Initialize.

    Args:
      output_path: The path for the metrics report.  If empty, no metrics are
          collected.
    """
    self._output_path = output_path
    self._old_enabled = None  # Set in __enter__.

  def __enter__(self):
    global _enabled
    self._old_enabled = _enabled
    _enabled = bool(self._output_path)

  def __exit__(self, exc_type, exc_value, traceback):
    global _enabled
    _enabled = self._old_enabled
    if self._output_path:
      with open(self._output_path, "w") as f:
        f.write(_get_report())
