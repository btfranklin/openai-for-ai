from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openai_for_ai.parser import parse_operations, parse_schemas


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = {
            "openapi": "3.1.0",
            "paths": {
                "/assistants": {
                    "get": {
                        "operationId": "listAssistants",
                        "summary": "List assistants",
                        "tags": ["Assistants"],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": (
                                                "#/components/schemas/"
                                                "ListAssistantsResponse"
                                            )
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "ListAssistantsResponse": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "description": (
                                    "Assistants available to the user."
                                ),
                            }
                        },
                        "required": ["data"],
                    }
                }
            },
        }

    def test_parse_operations_extracts_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = parse_operations(self.spec, sha="123abc", out_dir=out_dir)

        self.assertEqual(len(result.all_operations), 1)
        block = result.all_operations[0]
        self.assertEqual(block.block_id, "assistants.listAssistants")
        self.assertEqual(block.method, "GET")
        self.assertEqual(block.path, "/assistants")
        self.assertEqual(block.models_out, ["ListAssistantsResponse"])
        self.assertEqual(block.tag, "Assistants")
        self.assertEqual(block.responses[0]["status"], "200")
        self.assertEqual(
            block.responses[0]["content"][0]["schema_ref"],
            "ListAssistantsResponse",
        )

    def test_parse_schemas_includes_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            schemas = parse_schemas(self.spec, sha="123abc", out_dir=out_dir)

        self.assertEqual(len(schemas), 1)
        schema = schemas[0]
        self.assertEqual(schema.name, "ListAssistantsResponse")
        self.assertTrue(schema.properties[0]["required"])

    def test_parse_schemas_any_of_normalization(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "Foo": {"type": "object"},
                    "Bar": {"type": "object"},
                    "Union": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/Foo"},
                            {"type": "string", "description": "Inline"},
                        ]
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            schemas = parse_schemas(spec, sha="abc123", out_dir=out_dir)

        union = next(s for s in schemas if s.name == "Union")
        self.assertEqual(union.any_of[0]["schema_ref"], "Foo")
        self.assertEqual(union.any_of[1]["schema"].get("type"), "string")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
