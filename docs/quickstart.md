# Quickstart

## Goal: I want to try out type-checking.

1. Install pytype.

    ```shell
    pip install pytype
    ```

2. Run pytype on a project.

    ```shell
    pytype [file or directory]
    ```

## Goal: I want to add type annotations to a Python project.

1. Install pytype.

    ```shell
    pip install pytype
    ```

2. Run pytype on a project.

    ```shell
    pytype [file or directory]
    ```

3. Merge type annotations into each of the project's modules.

    ```shell
    merge-pyi -i [module].py pytype_output/[module].pyi
    ```

## Goal: I want to set up regular type-checking for a project.

1. Install pytype.

    ```shell
    pip install pytype
    ```

2. Create/modify the project's `setup.cfg` with pytype options.

    ```shell
    cd [project]
    pytype --generate-config=pytype.cfg
    [edit pytype.cfg]
    cat pytype.cfg >> setup.cfg
    rm pytype.cfg
    ```

3. Run pytype, then fix the code and/or edit `setup.cfg` until there are no
more errors.

    ```shell
    pytype .
    [fix type errors and/or edit setup.cfg]
    ```

4. Check in the new `setup.cfg`.

Remember to regularly run pytype or add it to your automated scripts.
