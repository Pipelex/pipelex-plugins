from __future__ import annotations

import os
import shutil

import pytest


@pytest.fixture(scope="session")
def node() -> str:
    """The `node` the hook bundle runs on. Skipped without one on a developer machine, never in CI.

    A gate that skips in CI is a green light for nothing, so under `CI` a missing `node` is a failure
    and `tests.yml` installs one.
    """
    found = shutil.which("node")
    if found is None:
        if os.environ.get("CI"):
            pytest.fail("no node on the PATH under CI: the hook tests must run there, and tests.yml installs Node for them")
        pytest.skip("no node on the PATH")
    return found
