# Pylint Blocking Calls Checker

This is a pylint plugin that checks for blocking calls in your async python code.

## Quickstart

### Installation

The best way to install the plugin is to use pip as follows:
```bash
pip install pylint-blocking-calls
```

### Usage

Let's start with an example:

```python
import asyncio
import time


def blocking_function():
    time.sleep(5)  # an example of an IO-bound operation


async def async_function():
    blocking_function()  # <- This call blocks the event loop!


def some_another_function():
    blocking_function()


async def async_function2():
    some_another_function()  # <- This call also implicitly blocks the event loop.


async def main():
    time_before = time.time()
    await asyncio.gather(async_function(), async_function2())
    time_after = time.time()

    # This can take 5 seconds but actually takes 10, because both async functions block the event loop
    print(f"Time elapsed: {(time_after - time_before):.0f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
```

Save the file with the name "example.py" and run the following command:

```bash
BLOCKING_FUNCTION_NAMES="^blocking_function$" pylint --load-plugins=pylint_blocking_calls example.py
```

This should provide the following output:
```bash
************* Module example
...............
example.py:10:4: W0002: blocking_function (blocking-call)
example.py:18:4: W0002: some_another_function -> blocking_function (blocking-call)

-----------------------------------
Your code has been rated at 4.12/10
```

### Plugin configuration

Plugin supports configuration via the following environment variables:
```bash
# required
export BLOCKING_FUNCTION_NAMES="" # comma-separated list of regexps that match blocking function names in your project

# optional
export SKIP_FUNCTIONS="" # comma-separated list of regexps that match function names that should be skipped
export SKIP_MODULES=""  # comma-separated list of regexps that match module names that should be skipped
export SKIP_DECORATED="" # comma-separated list of regexps that match decorator names that should be skipped
```

See the [tests/test_checker.py](./tests/test_checker.py) file for a real configuration example.

### Production setup

The plugin is designed to be used in a CI/CD pipeline.

> **_NOTE:_**  When running on a multiple files, you must run pylint with the single process mode (`--jobs=1`), otherwise there could be a race condition and the plugin may be not working correctly.

Consider the following workaround in production:
```bash
# ... as a part of your CI/CD pipeline
export BLOCKING_FUNCTION_NAMES="...."
export SKIP_FUNCTIONS="...."
export SKIP_MODULES="...."
export SKIP_DECORATED="...."
# run pylint with multiple cores for better performance
pylint --disable=blocking-call $(REPO_DIR)/src
# run pylint with a single core to check for blocking calls
pylint -j 1 --disable=all --enable=blocking-call $(REPO_DIR)/src
```

## Development

### Install dependencies

Prerequisites:
- python 3.11 installed
- poetry installed

To install the dependencies, run:
```shell
poetry install --no-root
poetry shell
```

The `--no-root` flag is important to install only dependencies, not the project itself.

### Run tests

Run tests with the command:
```shell
PYTHONPATH="$PYTHONPATH:$PWD" poetry run pytest tests/
```

## Motivation

This plugin was created to help us find blocking calls in our async code. 

We use it in our CI pipeline to prevent blocking calls from being merged into the master branch.

Please share your feedback and ideas in the issues section.

## External links

View the plugin page on [PyPi](https://pypi.org/project/pylint-blocking-calls/).
