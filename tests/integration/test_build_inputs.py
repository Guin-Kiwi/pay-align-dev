"""Check the pinned Python base image and dependency locks."""

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]


def test_python_312_base_image_is_pinned_by_digest():
    base = next(line for line in (ROOT / "Dockerfile").read_text().splitlines()
                if line.startswith("FROM "))
    assert re.fullmatch(
        r"FROM python:3\.12(?:\.\d+)?-slim(?:-[a-z]+)?@sha256:[0-9a-f]{64}", base
    ), "The Python 3.12 base image must have an immutable digest"


def lock_lines(filename):
    contents = (ROOT / filename).read_text().replace("\\\n", " ")
    return [line.strip() for line in contents.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-dev.txt"])
def test_every_locked_dependency_has_an_exact_version_and_sha256_hash(filename):
    requirements = lock_lines(filename)
    assert requirements, "The dependency lock must not be empty"
    for line in requirements:
        declaration, *hashes = line.split("--hash=")
        requirement = Requirement(declaration.strip())
        pins = list(requirement.specifier)
        assert len(pins) == 1 and pins[0].operator == "==" and "*" not in pins[0].version, (
            f"{requirement.name} needs one exact version"
        )
        assert hashes and all(re.fullmatch(r"sha256:[0-9a-f]{64}", value.strip())
                              for value in hashes), f"{requirement.name} needs SHA-256 hashes"


def test_development_lock_preserves_runtime_dependency_versions():
    runtime = [Requirement(line.split("--hash=")[0].strip())
               for line in lock_lines("requirements.txt")]
    development = {}
    for line in lock_lines("requirements-dev.txt"):
        requirement = Requirement(line.split("--hash=")[0].strip())
        development[requirement.name] = requirement.specifier
    for requirement in runtime:
        assert development.get(requirement.name) == requirement.specifier, requirement.name
