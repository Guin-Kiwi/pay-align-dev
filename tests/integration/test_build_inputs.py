"""Guard the Docker investigation's requirement for fixed build inputs."""

import re
from pathlib import Path

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


def test_every_locked_dependency_has_an_exact_version_and_sha256_hash():
    requirements = lock_lines("requirements.txt")
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

