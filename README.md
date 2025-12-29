# openai-for-ai

![openai-for-ai banner](https://raw.githubusercontent.com/btfranklin/openai-for-ai/main/.github/social%20preview/openai-for-ai_social_preview.png "openai-for-ai")

A CLI for compiling the OpenAI OpenAPI specification into deterministic, LLM-friendly HTML blocks and discovery manifests.

## Usage

```shell
pdm install
pdm run openai-for-ai build --spec-url https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml --out site/
```

This fetches the latest spec (with ETag-based caching), renders operation and component pages beneath `site/`, and generates helper indexes such as `llms.txt`, `manifest.json`, and `blocks/index.json`.

Use `pdm run openai-for-ai build --help` to see all available options.

## CLI Examples

```shell
pdm run openai-for-ai build --spec-url https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml --out site/
```
- `--spec-url` fetches the published OpenAI OpenAPI document and respects the built-in ETag cache to avoid redundant downloads.
- `--out site/` writes the rendered HTML fragments and indexes into the `site/` directory that ships with the repo.

```shell
pdm run openai-for-ai build
```
- With no flags, the builder uses the default remote spec, writes into `site/`, and includes the default language examples (`curl`, `python`).

```shell
pdm run openai-for-ai build --spec-path tests/data/openai.documented.yml --out tmp/site-preview
```
- `--spec-path` reuses the bundled fixture for deterministic local runs.
- `--out tmp/site-preview` keeps the generated files in a disposable directory so the canonical `site/` folder stays untouched.

```shell
pdm run openai-for-ai build --spec-url https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml --lang javascript --out site/
```
- `--lang javascript` renders blocks optimized for JavaScript code samples.
- Combining `--lang` with an explicit `--out` lets you produce language-specific previews without overwriting other assets.

## Tests

```shell
pdm run pytest
```

The integration tests exercise the full build pipeline against the real OpenAI OpenAPI specification bundled under `tests/data/openai.documented.yml`. Ensure optional dependencies (e.g., Jinja2) are installed so these tests execute instead of being skipped.

## License

This project is licensed under the [MIT License](LICENSE).
