"""Test configuration: give the module-level app a valid DATABASE_URL.

`create_app()` requires DATABASE_URL (ADR-005). Tests that import the
module-level `app` therefore need one; in-memory SQLite is for tests only.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
