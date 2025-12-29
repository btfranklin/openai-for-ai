from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openai_for_ai.parser import (
    collect_examples,
    parse_operations,
    parse_schemas,
)


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

    def test_parse_operations_collects_nested_models(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/widgets": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": (
                                                "#/components/schemas/"
                                                "Widget"
                                            )
                                        },
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "anyOf": [
                                                {
                                                    "$ref": (
                                                        "#/components/"
                                                        "schemas/"
                                                        "WidgetResponse"
                                                    )
                                                },
                                                {"type": "string"},
                                            ]
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
                    "Widget": {"type": "object"},
                    "WidgetResponse": {"type": "object"},
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = parse_operations(spec, sha="123abc", out_dir=out_dir)

        block = result.all_operations[0]
        self.assertEqual(block.models_in, ["Widget"])
        self.assertEqual(block.models_out, ["WidgetResponse"])

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

    def test_parse_operations_resolves_parameter_refs(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/widgets": {
                    "get": {
                        "parameters": [
                            {"$ref": "#/components/parameters/LimitParam"}
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
            "components": {
                "parameters": {
                    "LimitParam": {
                        "name": "limit",
                        "in": "query",
                        "description": "Max results",
                        "schema": {"type": "integer"},
                    }
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = parse_operations(spec, sha="123abc", out_dir=out_dir)

        block = result.all_operations[0]
        self.assertEqual(len(block.parameters), 1)
        param = block.parameters[0]
        self.assertEqual(param["name"], "limit")
        self.assertEqual(param["in"], "query")
        self.assertEqual(param["type"], "integer")
        self.assertEqual(param["description"], "Max results")

    def test_parse_operations_prefers_operation_parameters(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/widgets/{widget_id}": {
                    "parameters": [
                        {
                            "name": "widget_id",
                            "in": "path",
                            "required": False,
                            "description": "path default",
                            "schema": {"type": "string"},
                        }
                    ],
                    "get": {
                        "parameters": [
                            {
                                "name": "widget_id",
                                "in": "path",
                                "required": True,
                                "description": "operation override",
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "OK"}},
                    },
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = parse_operations(spec, sha="123abc", out_dir=out_dir)

        block = result.all_operations[0]
        self.assertEqual(len(block.parameters), 1)
        self.assertTrue(block.parameters[0]["required"])
        self.assertEqual(
            block.parameters[0]["description"],
            "operation override",
        )

    def test_collect_examples_includes_falsy_values(self) -> None:
        examples = collect_examples({"example": 0})
        self.assertEqual(examples[0]["label"], "default")
        self.assertEqual(examples[0]["value"], 0)

        examples = collect_examples({"example": ""})
        self.assertEqual(examples[0]["value"], "")

        examples = collect_examples({"example": False})
        self.assertEqual(examples[0]["value"], False)

    def test_parse_operations_sanitizes_tag_paths(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/weird": {
                    "get": {
                        "tags": ["../Weird/Tag"],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = parse_operations(spec, sha="123abc", out_dir=out_dir)

        block = result.all_operations[0]
        self.assertTrue(block.output_path.is_relative_to(out_dir))
        self.assertEqual(block.output_path.parent.name, "Weird-Tag")

    def test_parse_schemas_sanitizes_schema_paths(self) -> None:
        spec = {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "../Danger/Schema": {"type": "object"},
                }
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            schemas = parse_schemas(spec, sha="abc123", out_dir=out_dir)

        schema = schemas[0]
        self.assertTrue(schema.output_path.is_relative_to(out_dir))
        self.assertEqual(schema.output_path.name, "Danger-Schema.html")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
