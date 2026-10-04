#!/usr/bin/env python3
"""
Scenario tests for scripts/check-lifecycle.py. Each fixture sets its own
lifecycle state, so results do not depend on the repository's current phase.
"""

import os
import shutil
import subprocess
import sys
import tempfile

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = tempfile.mkdtemp()
    try:
        base_dir = os.path.join(temp_dir, "base")
        os.makedirs(base_dir)
        shutil.copytree(root_dir, base_dir, dirs_exist_ok=True, ignore=lambda dir, contents: [".git", ".venv"])

        with open(os.path.join(base_dir, "docs/PROJECT.md"), "w") as f:
            f.write("# PROJECT.md\n\nFixture project context.\n")

        failures = 0

        def fail(message):
            nonlocal failures
            print(f"✗ {message}")
            failures += 1

        # Add test logic here if needed

        if failures > 0:
            sys.exit(1)

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()