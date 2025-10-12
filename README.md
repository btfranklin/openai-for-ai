# openai-for-ai

A CLI for compiling the OpenAI OpenAPI specification into deterministic, LLM-friendly HTML blocks and discovery manifests.

## Usage

```shell
pdm install
pdm run openai-for-ai build --spec-url https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml --out site/
```

This fetches the latest spec (with ETag-based caching), renders operation and component pages beneath `site/`, and generates helper indexes such as `llms.txt`, `manifest.json`, and `blocks/index.json`.

Use `pdm run openai-for-ai build --help` to see all available options.

## Tests

```shell
pdm run pytest
```

The integration tests exercise the full build pipeline against the real OpenAI OpenAPI specification bundled under `tests/data/openai.documented.yml`. Ensure optional dependencies (e.g., Jinja2) are installed so these tests execute instead of being skipped.

## License

This project is licensed under the [MIT License](LICENSE).
