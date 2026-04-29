# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/`. Grammar loading and orchestration are under `src/grammar/` and `src/config_utils/`; search code is in `src/search/`; the Streamlit editor pages are in `src/pages/`. Configuration data and JSON schemas live in `config/`, with active Tira configs in `config/tira/` and minimal examples in `config/example/`. Test coverage is in `tests/`. Utility scripts for data generation and migration live in `scripts/`. Treat `deprecated/` as reference-only unless a task explicitly targets legacy code.

## Build, Test, and Development Commands
Use the existing environment:

```bash
source .venv/bin/activate
```

Run the Streamlit editor with `CONFIG_DIR=./config streamlit run src/app.py`. Set `CONFIG_DIR` to `config/tira` or another config root when testing editor changes.

Don't run any tests or execute code. Let the user handle this.

## Coding Style & Naming Conventions
Use 4-space indentation and follow existing Python style with type hints on new or changed code. Modules and functions use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`. Keep Streamlit page state helpers and registry logic separate rather than mixing UI and parsing code. No formatter or linter is configured in the repo, so match surrounding style and keep imports and docstrings consistent with nearby files.

## Testing Guidelines
Tests use `pytest`, and files follow the existing `*_test.py` pattern in `tests/`. Prefer narrow unit tests for registry, parser, and editor-state behavior before broader end-to-end coverage. When changing config-driven logic, add or update fixture data under `config/example/` or `data/test_cases/` only when the test depends on it.

## Commit & Pull Request Guidelines
Don't make commits or pull requests yourself, let the user handle this.

## Configuration Tips
`CONFIG_DIR` controls which YAML tree the app loads; `src/config_utils/config_walker.py` defaults it to `./config`. Validate schema-sensitive edits against `config/schemas/` and avoid editing production-like `config/tira/` files without a clear reason.
