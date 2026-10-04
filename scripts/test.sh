#!/usr/bin/env python3

import os
import subprocess
import sys

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)

    python = "python"
    if os.name == "nt" and os.path.exists(".venv\\Scripts\\python.exe"):
        python = ".venv\\Scripts\\python.exe"
    elif os.path.exists(".venv/bin/python"):
        python = ".venv/bin/python"

    try:
        subprocess.run([python, "-m", "pytest", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"✗ pytest is not installed for {python}; run: python -m pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    # Run checks
    subprocess.run([python, "scripts/check-lifecycle.py"], check=True)
    subprocess.run([python, "scripts/test-lifecycle.py"], check=True)
    subprocess.run([python, "-m", "unittest", "discover", "-s", "scripts/tests", "-q"], check=True)
    subprocess.run([python, "-m", "pytest", "-q"], check=True)

if __name__ == "__main__":
    main()
