from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from openai_for_ai.spec import load_spec


class FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict[str, str] | None] = []

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        self.calls.append(headers)
        return next(self._responses)

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class SpecTests(unittest.TestCase):
    def test_load_spec_retries_when_etag_cache_missing(self) -> None:
        spec_url = "https://example.com/spec.yml"
        raw_spec = (
            "openapi: 3.1.0\n"
            "info:\n"
            "  title: Test\n"
            "  version: '1'\n"
            "paths: {}\n"
        )
        request = httpx.Request("GET", spec_url)
        responses = [
            httpx.Response(304, request=request),
            httpx.Response(
                200,
                request=request,
                content=raw_spec.encode("utf-8"),
                headers={"ETag": "newtag"},
            ),
        ]
        client = FakeClient(responses)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            (cache_dir / "openapi.etag").write_text("oldtag")
            with patch(
                "openai_for_ai.spec.httpx.Client",
                return_value=client,
            ):
                spec, sha = load_spec(spec_url, cache_dir=cache_dir)

            spec_path = cache_dir / "openapi.yml"
            self.assertTrue(spec_path.exists())
            self.assertEqual(spec_path.read_text(), raw_spec)

        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertEqual(len(sha), 12)
        self.assertEqual(client.calls[0], {"If-None-Match": "oldtag"})
        self.assertIn(client.calls[1], (None, {}))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
