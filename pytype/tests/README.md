# Pytype Functional Tests

This directory contains functional tests for Pytype. They target the same Python
version that pytype is running under; as of August 2021, the pytype tests run in
Python 3.6 - 3.9.

## Adding New Tests

Adding a new test method to an existing functional test class is straightforward
and does not need any special care. When adding a new test class, the new class
should subclass `test_base.BaseTest`. When adding a new test module, the module
should include a call to `test_base.main` as follows (replacing the typical
`unittest.main` call):

```
if __name__ == "__main__":
  test_base.main()
```
