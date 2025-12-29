from __future__ import annotations

import unittest

from markupsafe import Markup

from openai_for_ai.utils import (
    collect_parameters,
    markdown_links_to_html,
    normalize_path_to_slug,
)


class UtilsTests(unittest.TestCase):
    def test_normalize_path_to_slug(self) -> None:
        self.assertEqual(
            normalize_path_to_slug("/assistants/{assistant_id}"),
            "assistants-{assistant_id}",
        )
        self.assertEqual(
            normalize_path_to_slug("//audio//speech"),
            "audio-speech",
        )

    def test_collect_parameters_deduplicates(self) -> None:
        merged = collect_parameters(
            [
                {"name": "assistant_id", "in": "path", "required": True},
                {"name": "limit", "in": "query"},
            ],
            [
                {"name": "assistant_id", "in": "path", "required": True},
                {"name": "order", "in": "query"},
            ],
        )
        self.assertEqual(len(merged), 3)
        names = {(p["name"], p["in"]) for p in merged}
        self.assertIn(("assistant_id", "path"), names)
        self.assertIn(("limit", "query"), names)
        self.assertIn(("order", "query"), names)

    def test_markdown_links_to_html(self) -> None:
        rendered = markdown_links_to_html(
            "Read the [docs](https://example.com/docs)."
        )
        self.assertIsInstance(rendered, Markup)
        self.assertIn(
            '<a href="https://example.com/docs">docs</a>',
            str(rendered),
        )
        self.assertTrue(str(rendered).startswith("Read the "))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
