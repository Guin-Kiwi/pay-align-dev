"""Clean Architecture dependency rule: dependencies point inward.

domain <- application <- interfaces <- infrastructure
A layer may import only itself and layers further in; domain and application
must not import web or database frameworks.
"""

import ast
import os
import pathlib
import tempfile
import unittest

APP = pathlib.Path(__file__).resolve().parents[2] / "src" / "app"
LAYERS = ["domain", "application", "interfaces", "infrastructure"]
FRAMEWORKS = {"fastapi", "starlette", "sqlalchemy", "flask", "django"}
FRAMEWORK_FREE = {"domain", "application"}


def _imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def violations(app_dir):
    found = []
    for rank, layer in enumerate(LAYERS):
        for path in sorted((app_dir / layer).rglob("*.py")):
            for module in _imports(path):
                parts = module.split(".")
                if parts[0] == "app" and len(parts) > 1 and parts[1] in LAYERS:
                    if LAYERS.index(parts[1]) > rank:
                        found.append(f"{path.relative_to(app_dir)}: {layer} imports outer layer {module}")
                if layer in FRAMEWORK_FREE and parts[0] in FRAMEWORKS:
                    found.append(f"{path.relative_to(app_dir)}: {layer} imports framework {module}")
    return found


class DependencyRuleTests(unittest.TestCase):
    def test_project_follows_the_dependency_rule(self):
        self.assertEqual(violations(APP), [])

    def test_detects_inner_layer_importing_outer_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = pathlib.Path(tmp)
            for layer in LAYERS:
                (app / layer).mkdir()
            (app / "domain" / "user.py").write_text("from app.infrastructure.db import Session\n")
            (app / "application" / "service.py").write_text("import sqlalchemy\n")
            (app / "infrastructure" / "db.py").write_text("from app.domain.user import User\n")
            found = violations(app)
        self.assertEqual(len(found), 2)
        self.assertIn("domain imports outer layer app.infrastructure.db", found[0])
        self.assertIn("application imports framework sqlalchemy", found[1])


if __name__ == "__main__":
    unittest.main()
