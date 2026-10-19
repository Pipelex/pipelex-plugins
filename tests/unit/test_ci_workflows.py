"""Every workflow runs its jobs with `DO_NOT_TRACK=1`, as the usage-statistics specification's rule R8 requires.

The workflow-level `env:` sets it, so a job added later inherits it the day it appears. A job, a step, a job's
container or service, or a step's script could still set it again for its own scope, so wherever it is set it must
be `1`, and no script unsets it. The workflows are discovered, never listed. The same walk verifies the conformance
repository's own workflows (`conformance/ci_workflows.py` in the workspace).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator

WORKFLOWS_DIR = Path(__file__).parents[2] / ".github" / "workflows"
DO_NOT_TRACK = "DO_NOT_TRACK"
DO_NOT_TRACK_ON = "1"

# A script line that gives the variable anything but `1`, in a shell assignment, an `export` or a line written to
# `$GITHUB_ENV`, or that unsets it with `unset` or `env -u`. A line that only reads the variable, and a whole-line
# comment, do not count.
SCRIPT_ASSIGNMENT = re.compile(rf"(?<![\w.$]){DO_NOT_TRACK}=(?![\"']?{DO_NOT_TRACK_ON}[\"']?(?:[\s;&|)]|$))")
SCRIPT_UNSET = re.compile(rf"\bunset\b[^\n;&|]*\b{DO_NOT_TRACK}\b|(?:\s-u\s*|--unset=){DO_NOT_TRACK}\b")

OVERRIDING_WORKFLOW = """
env:
  DO_NOT_TRACK: "1"
jobs:
  a:
    env:
      DO_NOT_TRACK: "0"
    container:
      image: node
      env:
        DO_NOT_TRACK: ""
    services:
      db:
        image: postgres
        env:
          DO_NOT_TRACK: "false"
    steps:
      - env:
          DO_NOT_TRACK: "1"
        run: echo "$DO_NOT_TRACK"
      - env:
          DO_NOT_TRACK: "0"
        run: true
      - run: export DO_NOT_TRACK=0
      - run: echo "DO_NOT_TRACK=" >> "$GITHUB_ENV"
      - run: unset DO_NOT_TRACK
      - run: env -u DO_NOT_TRACK make test
      - run: |
          # DO_NOT_TRACK=0 is what this comment mentions
          DO_NOT_TRACK=1 make test
"""
OVERRIDING_SCOPES = [
    "jobs.a.env",
    "jobs.a.container.env",
    "jobs.a.services.db.env",
    "jobs.a.steps[1].env",
    "jobs.a.steps[2].run",
    "jobs.a.steps[3].run",
    "jobs.a.steps[4].run",
    "jobs.a.steps[5].run",
]


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.y*ml"))


def _load(text: str) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(text))


def _mapping(value: object) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _steps(job: dict[str, Any]) -> list[Any]:
    steps = job.get("steps")
    return cast("list[Any]", steps) if isinstance(steps, list) else []


def _env_scopes(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every `env:` below the workflow's own: each job's, its container's and services', and each step's."""
    for job_id, job_value in _mapping(document.get("jobs")).items():
        job = _mapping(job_value)
        yield f"jobs.{job_id}.env", _mapping(job.get("env"))
        yield f"jobs.{job_id}.container.env", _mapping(_mapping(job.get("container")).get("env"))
        for service_id, service in _mapping(job.get("services")).items():
            yield f"jobs.{job_id}.services.{service_id}.env", _mapping(_mapping(service).get("env"))
        for index, step in enumerate(_steps(job)):
            yield f"jobs.{job_id}.steps[{index}].env", _mapping(_mapping(step).get("env"))


def _scripts(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for job_id, job_value in _mapping(document.get("jobs")).items():
        for index, step in enumerate(_steps(_mapping(job_value))):
            script = _mapping(step).get("run")
            if isinstance(script, str):
                yield f"jobs.{job_id}.steps[{index}].run", script


def _script_overrides(script: str) -> bool:
    lines = (line for line in script.splitlines() if not line.lstrip().startswith("#"))
    return any(SCRIPT_ASSIGNMENT.search(line) or SCRIPT_UNSET.search(line) for line in lines)


def _overriding_scopes(document: dict[str, Any]) -> list[str]:
    """Where a workflow sets `DO_NOT_TRACK` below its top level to anything but `1`, or unsets it in a script."""
    scopes = [scope for scope, env in _env_scopes(document) if DO_NOT_TRACK in env and str(env[DO_NOT_TRACK]) != DO_NOT_TRACK_ON]
    scopes.extend(scope for scope, script in _scripts(document) if _script_overrides(script))
    return scopes


class TestCiWorkflows:
    def test_there_are_workflows_to_check(self) -> None:
        assert _workflow_files(), f"no workflow found under {WORKFLOWS_DIR}: the checks below would pass vacuously"

    @pytest.mark.parametrize("workflow", _workflow_files(), ids=lambda path: path.name)
    def test_every_workflow_sets_do_not_track_for_all_its_jobs(self, workflow: Path) -> None:
        value = _mapping(_load(workflow.read_text(encoding="utf-8")).get("env")).get(DO_NOT_TRACK)
        assert value == DO_NOT_TRACK_ON, f'{workflow.name} must set `DO_NOT_TRACK: "1"` in its workflow-level `env:`, not {value!r}'

    @pytest.mark.parametrize("workflow", _workflow_files(), ids=lambda path: path.name)
    def test_no_job_or_step_switches_usage_statistics_back_on(self, workflow: Path) -> None:
        scopes = _overriding_scopes(_load(workflow.read_text(encoding="utf-8")))
        assert scopes == [], (
            f"{workflow.name} sets DO_NOT_TRACK to something other than 1, or unsets it, in {scopes}, which wins over the workflow-level env"
        )

    def test_the_walk_finds_every_scope_that_switches_it_back_on(self) -> None:
        """Each `env:` scope, an `export`, a `$GITHUB_ENV` line, an `unset` and an `env -u` are found.

        Setting it to `1`, reading it or naming it in a comment is not.
        """
        assert _overriding_scopes(_load(OVERRIDING_WORKFLOW)) == OVERRIDING_SCOPES
