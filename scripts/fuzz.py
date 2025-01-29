"""
Helper script to generate a matrix of package name and fuzz tests for a Go
project.

The output is a JSON matrix ready to be used in a GitHub Action with the fromJSON function in
the following format:

```json
[
  {
    "name": "FuzzTake",
    "pkg": "github.com/FollowTheProcess/parser"
  },
  {
    "name": "FuzzExact",
    "pkg": "github.com/FollowTheProcess/parser"
  },
  {
    "name": "FuzzExactCaseInsensitive",
    "pkg": "github.com/FollowTheProcess/parser"
  }
]
```

Where `name` is the name of the test function, and `pkg` is the package it lives in.

Expected usage is to then feed this into a matrix like so:

```yaml
strategy:
  matrix:
    include: ${{ fromJSON(needs.matrix.outputs.json) }}
```

Where there is a previous job that runs this script and redirects the output to $GITHUB_OUTPUT like so:

```yaml
- name: Make Fuzz Matrix
  id: matrix
  run: echo "matrix=$(python script.py)" >> $GITHUB_OUTPUT
```

If there are no fuzz tests, the script simply prints '[]'.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class Test:
    """
    A Test represents a single line of go test -json output.
    """

    time: str
    action: str
    package: str
    output: str

    @staticmethod
    def parse(raw: str) -> Test:
        """
        Parse a Test from a line of JSONL.
        """
        record: dict[str, str] = json.loads(raw)
        return Test(
            time=record.get("Time", "").strip(),
            action=record.get("Action", "").strip(),
            package=record.get("Package", "").strip(),
            output=record.get("Output", "").strip(),
        )


def list_tests() -> list[str]:
    """
    Runs go list ./... with flags to return information about
    Go packages that contain Fuzz tests.

    It returns a list of JSON lines.
    """
    output = subprocess.run(
        [
            "go",
            "test",
            "-list",
            "^Fuzz",
            "-run",
            "^$",
            "-json",
            "./...",
        ],
        check=True,
        shell=False,
        capture_output=True,
    ).stdout.decode()

    return output.strip().splitlines()


def parse_lines(lines: list[str]) -> Iterator[Test]:
    """
    Takes a list of JSON lines and parses them into our Test record.
    """
    for line in lines:
        yield Test.parse(line)


def fuzz_filter(tests: Iterator[Test]) -> Iterator[Test]:
    """
    Filters an incoming stream of Test for those containing an output
    of FuzzXXX.
    """
    for test in tests:
        if test.output.startswith("Fuzz"):
            yield test


def collect(tests: Iterator[Test]) -> list[dict[str, str]]:
    """
    Collect a stream of Tests into the final output expected as a GitHub
    actions matrix.
    """
    return [{"name": test.output, "pkg": test.package} for test in tests]


if __name__ == "__main__":
    tests = collect(fuzz_filter(parse_lines(list_tests())))
    print(json.dumps(tests))
