from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    import jinja2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency for tests
    jinja2 = None  # type: ignore[assignment]

if jinja2 is not None:  # pragma: no branch - simplify import control
    from openai_for_ai.builder import BuildConfig, build
else:  # pragma: no cover - import fallback for skipped tests
    BuildConfig = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]


class BuilderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if jinja2 is None or BuildConfig is None or build is None:
            self.skipTest("Jinja2 dependency is not installed")
        self.spec_path = Path(__file__).parent / "data" / "openai.documented.yml"
        if not self.spec_path.exists():
            self.skipTest("Spec fixture is not available")

    def test_build_with_real_spec_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            config = BuildConfig(
                spec_url=self.spec_path,
                out_dir=out_dir,
                languages=["curl"],
            )
            result = build(config)

            manifest_path = out_dir / "manifest.json"
            llms_path = out_dir / "llms.txt"

            self.assertTrue(manifest_path.exists(), "manifest.json was not created")
            self.assertTrue(llms_path.exists(), "llms.txt was not created")

            manifest = json.loads(manifest_path.read_text())
            self.assertGreater(len(manifest), 0)
            self.assertIn("listAssistants", manifest)

            llms_body = llms_path.read_text()
            self.assertTrue(llms_body.startswith("# "))
            self.assertIn("## OPTIONAL", llms_body)

            stream_event_path = out_dir / "components" / "schemas" / "ResponseStreamEvent.html"
            if stream_event_path.exists():
                html = stream_event_path.read_text()
                self.assertIn("<ul>", html)
                self.assertNotIn("$ref", html)

            self.assertGreater(result["block_count"], 0)
            self.assertGreater(result["schema_count"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
