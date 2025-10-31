Canvas3D — Deterministic 3D Scene Spec Validator and Blender Add-on

Overview
Canvas3D provides a strict, deterministic scene specification contract and safe execution pipelines for Blender. It includes:
- A JSON schema and Python validator for scene specs
- A deterministic spec executor with atomic commit/rollback
- A restricted code execution sandbox and cleanup utilities
- Traversability checks (A* on a grid) and domain-specific rules
- CI, linting, type-checking, and pre-commit hooks for production readiness

Core docs and modules
- Schema summary: [docs/schema/SCHEMA_SUMMARY.md](docs/schema/SCHEMA_SUMMARY.md:1)
- JSON schema: [docs/schema/canvas3d_scene_spec.schema.json](docs/schema/canvas3d_scene_spec.schema.json:1)
- Spec validator: [canvas3d/utils/spec_validation.py](canvas3d/utils/spec_validation.py:1)
- Spec executor: [canvas3d/generation/spec_executor.py](canvas3d/generation/spec_executor.py:1)
- Scene builder (sandboxed): [canvas3d/generation/scene_builder.py](canvas3d/generation/scene_builder.py:1)
- Traversability: [canvas3d/utils/traversability.py](canvas3d/utils/traversability.py:1)
- LLM interface (OpenAI): [canvas3d/core/llm_interface.py](canvas3d/core/llm_interface.py:1)

What’s included
- Deterministic validation for versioned scene specs (v1.0.0)
- Domain rules for procedural_dungeon (grid required; door adjacency; corridor directions)
- Executor with:
  - Strict validation gate
  - RNG seeding via spec.seed
  - Build in temporary collection; atomic commit-or-rollback
  - Best-effort cleanup of new data-blocks
- Safe scene code sandbox with AST validation and runtime guards
- Traversability helpers (A*) and spec integration stubs
- Full test suite with green baseline
- Production tooling: [pyproject.toml](pyproject.toml:1), CI via [.github/workflows/ci.yml](.github/workflows/ci.yml:1), pre-commit via [.pre-commit-config.yaml](.pre-commit-config.yaml:1)

Requirements
- Python 3.10
- Blender (optional for full execution; not required for CI/tests)
- OpenAI API key (optional; for LLM features in [canvas3d/core/llm_interface.py](canvas3d/core/llm_interface.py:1))

Installation (developer/setup)
1) Create and activate a Python 3.10 environment.
2) Install in editable mode with dev extras:
   - python -m pip install -e .[dev]
3) (Optional) Install pre-commit hooks:
   - pre-commit install

Running tests
- Run the full test suite:
  - python -m pytest -q
- The suite validates:
  - Spec validation and schema contract
  - Sandbox (AST and runtime ops guard)
  - Spec executor atomic cleanup and deterministic naming
  - Traversability (A* and spec integration)

CI and quality gates
- GitHub Actions workflow: [.github/workflows/ci.yml](.github/workflows/ci.yml:1)
  - Lints with ruff, black, isort
  - Type-checks with mypy
  - Runs pytest on Ubuntu and Windows
- Pre-commit hooks: [.pre-commit-config.yaml](.pre-commit-config.yaml:1)
  - Trailing whitespace, EOF fix, YAML/TOML checks
  - ruff, black, isort, mypy
  - Quick pytest

Using the schema
- Read the concise guide: [docs/schema/SCHEMA_SUMMARY.md](docs/schema/SCHEMA_SUMMARY.md:1)
- Author JSON specs against: [docs/schema/canvas3d_scene_spec.schema.json](docs/schema/canvas3d_scene_spec.schema.json:1)
- Programmatic validation:
  - Use the API in [canvas3d/utils/spec_validation.py](canvas3d/utils/spec_validation.py:1)
  - For strict gating, call assert_valid_scene_spec(spec, expect_version="1.0.0") before execution

Deterministic spec execution (Blender or headless)
- The executor in [canvas3d/generation/spec_executor.py](canvas3d/generation/spec_executor.py:1) enforces:
  - strict validation gate
  - seeded randomness (spec.seed)
  - temporary collection build with atomic commit/rollback
- Outside Blender (bpy unavailable), set dry_run_when_no_bpy=True to validate and short-circuit safely.

Sandboxed scene code (advanced)
- [canvas3d/generation/scene_builder.py](canvas3d/generation/scene_builder.py:1) enforces:
  - AST-level validation against dangerous tokens/imports
  - Restricted globals (__builtins__) and safe importer
  - Runtime ops proxy to guard bpy.ops critical operations
- Intended for executing safe, generated Blender code snippets.

Traversability checks
- [canvas3d/utils/traversability.py](canvas3d/utils/traversability.py:1) provides:
  - astar_path_length, check_traversable, is_spec_traversable
  - Grid defaults, blocked cell derivation from spec, and min_path length enforcement
- Use to ensure start→goal paths meet constraints.

LLM integration (optional)
- [canvas3d/core/llm_interface.py](canvas3d/core/llm_interface.py:1) integrates with OpenAI Chat Completions:
  - Robust retry with backoff+jitter, token-bucket rate limiting
  - Circuit breaker
  - Strict JSON extraction, schema validation, and variants/ideas helpers
- Configure API endpoint/model and key via Add-on Preferences or environment (see your Blender add-on settings).

Blender add-on
- This repository follows Blender add-on structure and stubs register/unregister in modules.
- Install as an add-on by zipping the repository and using:
  - Blender → Edit → Preferences → Add-ons → Install… → select the zip
- Or develop in-place by placing the project under Blender’s scripts/addons path.

Development workflow
- Lint/type/test locally:
  - ruff check .
  - black --check .
  - isort --check-only .
  - mypy .
  - python -m pytest -q
- Pre-commit will run a consistent subset automatically on commit.
- The e2e probe script can be compiled for a basic smoke test: [tools/e2e_llm_probe.py](tools/e2e_llm_probe.py:1)

Front-end development:
- Prerequisite: Node.js
- From project root, in `front-end` folder run:
  - `npm install`
  - `npm run dev`
- To build production assets:
  - `npm run build`
- Built assets are copied into add-on package under `canvas3d/ui/frontend` by CI.
- The e2e probe script can be compiled for a basic smoke test: [tools/e2e_llm_probe.py](tools/e2e_llm_probe.py:1)

Versioning and changelog
- Semantic versioning planned. Track releases in CHANGELOG.md (to be introduced alongside release process).
- Current dev version: 0.1.0 (see [pyproject.toml](pyproject.toml:1))

License
- MIT (see [pyproject.toml](pyproject.toml:1) for license metadata)

Contributing
- Fork, create a feature branch, and open a PR.
- Ensure CI is green and pre-commit hooks pass locally.
- Align changes with schema and validator behavior documented in [docs/schema/SCHEMA_SUMMARY.md](docs/schema/SCHEMA_SUMMARY.md:1)
