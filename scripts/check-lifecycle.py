#!/usr/bin/env python3
"""
Checks that the AI-SDLC artefacts are present and consistent. Runs in CI.
"""

import os
import sys

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    failures = 0

    def fail(message):
        nonlocal failures
        print(f"✗ {message}")
        failures += 1

    def warn(message):
        print(f"⚠ {message}")
        if "GITHUB_ACTIONS" in os.environ:
            print(f"::warning::{message}")

    required_files = [
        "AGENTS.md", "LICENSE", "docs/INDEX.json", "docs/TASKS.md", 
        "docs/PROJECT.md", "docs/STANDARDS.md", "docs/AGENT-GUIDANCE.md",
        "docs/specs/UC-TEMPLATE.md", "docs/adr/ADR-TEMPLATE.md",
        ".github/copilot-instructions.md"
    ]

    for file_path in required_files:
        if not os.path.isfile(file_path):
            fail(f"missing {file_path}")

    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()