import unittest
from types import SimpleNamespace

NAV_LINKS = [
    "/", "/search", "/compare", "/ask", "/library", "/summarize", "/doc-compare",
    "/bookmarks", "/evaluation", "/analytics", "/system", "/demo",
]


class BaseNavTests(unittest.TestCase):
    def render(self, path):
        from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

        from config import ROOT

        child = DictLoader(
            {
                "child.html": "{% extends 'base.html' %}{% block crumb %}Compare methods{% endblock %}"
                "{% block content %}BODY{% endblock %}"
            }
        )
        env = Environment(
            loader=ChoiceLoader([child, FileSystemLoader(str(ROOT / "templates"))]),
            autoescape=True,
        )
        env.globals.update(
            url_for=lambda name, **kw: "/static/" + kw.get("filename", name),
            request=SimpleNamespace(path=path),
            get_flashed_messages=lambda **kw: [],
        )
        return env.get_template("child.html").render()

    def test_exactly_the_current_page_is_marked(self):
        html = self.render("/compare")
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertIn('href="/compare" class="active" aria-current="page"', html)

    def test_every_page_is_linked_and_icons_are_hidden_from_screen_readers(self):
        html = self.render("/")
        for href in NAV_LINKS:
            self.assertIn('href="%s"' % href, html)
        self.assertGreaterEqual(html.count('aria-hidden="true"'), len(NAV_LINKS))

    def test_skip_link_title_and_groups(self):
        html = self.render("/system")
        self.assertIn('href="#main"', html)
        self.assertIn('<main id="main"', html)
        self.assertIn("<title>Compare methods &middot; IntelliSearch</title>", html)
        for label in ("Search", "Documents", "Workspace", "Insights", "System"):
            self.assertIn('<div class="nav-label">%s</div>' % label, html)


if __name__ == "__main__":
    unittest.main()
