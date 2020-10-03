FROM python:3.7

# Tests try to create /nonexistent/path directory expecting it to fail.
# However, the directory can be created inside docker since running as root.
# File with same name makes the directory creation fail and serves as a
# workaround.
RUN touch /nonexistent

WORKDIR /app
RUN apt-get update && apt-get install -y bison flex cmake

COPY requirements.txt .
RUN pip3 install --no-cache -r requirements.txt

COPY . .
RUN python build_scripts/build.py

# Expected usage is to mount a local directory inside the container that
# contains python files that are going to be tested against pytype.
# Additionally the image is well suited for automated tests.
ENTRYPOINT ["/bin/bash"]
