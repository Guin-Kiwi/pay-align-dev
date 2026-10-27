import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "app" / "interfaces" / "static"


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def by_id(self):
        return {attrs["id"]: attrs for _, attrs in self.tags if "id" in attrs}


def node_binary():
    node = shutil.which("node")
    if node is None:
        pytest.fail("The browser UI tests require Node.js 22 on PATH.")
    return node


def page_javascript(client, page, rules=False):
    """Return the shared helpers followed by one page's script, as the browser loads them."""
    names = (("constants",) if rules else ()) + ("common", page)
    return "\n".join(client.get(f"/setup-assets/{name}.js").text for name in names)


def script_paths(page):
    return [str(STATIC / "common.js"), str(STATIC / f"{page}.js")]
