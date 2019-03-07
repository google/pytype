The main tests are the kythe verifier tests under testdata/

Get the latest [kythe
release](https://github.com/kythe/kythe/releases) and unpack it to `$HOME/kythe`. Then, to run a test (assuming `xref` is in your path):

````
xref testdata/testcase.py | ./kythe-verifier.sh testdata/testcase.py
````
