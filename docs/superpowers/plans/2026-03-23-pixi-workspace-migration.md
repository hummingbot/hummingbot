# Pixi Workspace Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform hummingbot from conda + setup.py into a pixi workspace with candles-feed as a workspace member.

**Architecture:** Pixi manages environments and dependencies via `[tool.pixi.*]` sections in `pyproject.toml`. Setuptools remains the build backend for Cython compilation only. candles-feed joins as a git submodule at `sub-packages/candles-feed/`.

**Tech Stack:** pixi (>=0.40), setuptools, Cython, conda-forge, git submodules

**Spec:** `docs/superpowers/specs/2026-03-23-pixi-workspace-migration-design.md`

**Notes:**
- The setup.py code in this plan is authoritative. The spec's setup.py block is stale — it incorrectly includes removed imports.
- The pre-commit config in this plan is authoritative. The spec's version omits the isort and detect-wallet-private-key hooks that must be preserved.
- CI workflow update (``.github/workflows/``) is OUT OF SCOPE for this branch. CI will reference deleted `setup/environment.yml` — a follow-up task is required before CI runs on this branch.
- `setup/environment_dydx.yml` is intentionally out of scope — it's a separate dydx-specific environment not used in the main workflow.
- `pytest-mock` and `pytest-cov` are NEW additions to dev dependencies (not present in current environment.yml).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | All project config: metadata, pixi workspace, deps, tools |
| `setup.py` | Modify | Cython-only build (strip metadata) |
| `.pre-commit-config.yaml` | Modify | flake8→ruff, add cython-lint |
| `.gitmodules` | Create | candles-feed submodule reference |
| `.gitattributes` | Create | pixi.lock binary diff rule |
| `.gitignore` | Modify | Add `.pixi/` |
| `.coveragerc` | Delete | Migrated to pyproject.toml |
| `.flake8` | Delete | Migrated to pyproject.toml |
| `setup/environment.yml` | Delete | Migrated to pixi sections |
| `setup/pip_packages.txt` | Delete | Migrated to pixi pypi-dependencies |

---

### Task 1: Create Branch and Git Infrastructure

**Files:**
- Create: `.gitmodules`
- Create: `.gitattributes`
- Modify: `.gitignore`

- [ ] **Step 1: Create the feature branch**

```bash
git checkout bleeding-edge
git checkout -b _for_bleed/pixi-workspace
```

- [ ] **Step 2: Add candles-feed as a git submodule**

```bash
git submodule add https://github.com/MementoRC/hb-candles-feed.git sub-packages/candles-feed
```

Verify: `ls sub-packages/candles-feed/pyproject.toml` exists.

- [ ] **Step 3: Create `.gitattributes`**

```
pixi.lock linguist-generated=true binary
```

- [ ] **Step 4: Add `.pixi/` to `.gitignore`**

Append to the end of `.gitignore`:

```
# Pixi
.pixi/
```

Do NOT add `pixi.lock` — it must be committed for reproducibility.

- [ ] **Step 5: Commit**

```bash
git add .gitmodules sub-packages/candles-feed .gitattributes .gitignore
git commit -m "chore: add candles-feed submodule and pixi git infrastructure"
```

---

### Task 2: Expand pyproject.toml — Project Metadata

**Files:**
- Modify: `pyproject.toml`

The current `pyproject.toml` has `[tool.pytest.ini_options]`, `[tool.black]`, `[build-system]`, and `[tool.isort]`. We add sections above and between them.

- [ ] **Step 1: Add `[project]` section**

Add at the top of `pyproject.toml`, before everything else:

```toml
[project]
name = "hummingbot"
version = "20260302"
description = "Hummingbot"
authors = [{name = "Hummingbot Foundation", email = "dev@hummingbot.org"}]
requires-python = ">=3.10"
license = {text = "Apache-2.0"}

[project.scripts]
hummingbot = "bin.hummingbot_quickstart:main"
```

Verified: `bin/__init__.py` exists and `bin/hummingbot_quickstart.py` has a callable `main()` at line 250.

- [ ] **Step 2: Add `[tool.setuptools.*]` sections**

Insert between `[build-system]` and `[tool.isort]`:

```toml
[tool.setuptools.packages.find]
include = ["hummingbot", "hummingbot.*"]
exclude = [
    "hummingbot.connector.gateway.clob_spot.data_sources.injective",
    "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual",
]

[tool.setuptools.package-data]
hummingbot = ["core/cpp/*", "VERSION", "templates/*TEMPLATE.yml"]
```

- [ ] **Step 3: Remove `conda_env` from `[tool.isort]`**

Delete the line `conda_env = "hummingbot"` from the existing `[tool.isort]` section. This setting is meaningless in a pixi environment.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add project metadata to pyproject.toml"
```

---

### Task 3: Expand pyproject.toml — Pixi Workspace and Dependencies

**Files:**
- Modify: `pyproject.toml`

This is the largest task. Add all pixi sections.

- [ ] **Step 1: Add pixi workspace config**

Add after the `[tool.setuptools.*]` sections:

```toml
[tool.pixi.workspace]
channels = ["conda-forge"]
platforms = ["linux-64", "osx-arm64"]
members = ["sub-packages/candles-feed"]
```

- [ ] **Step 2: Add pixi conda dependencies**

These are ALL packages from `setup/environment.yml` that are available on conda-forge. Add after the workspace section:

```toml
[tool.pixi.dependencies]
# Build/install
python = ">=3.10.12"
cython = ">=3.0.12"
setuptools = ">=80.8.0"
pip = ">=23.2.1"
# Core runtime
aiohttp = ">=3.8.5"
aioprocessing = ">=2.0.1"
aioresponses = ">=0.7.4"
aiounittest = ">=1.4.2"
async-timeout = ">=4.0.2,<5"
asyncssh = ">=2.13.2"
base58 = ">=2.1.1"
bidict = ">=0.22.1"
bip-utils = "*"
cachetools = ">=5.3.1"
cryptography = ">=41.0.2"
eth-account = ">=0.13.0"
injective-py = ">=1.12"
libta-lib = ">=0.6.4"
msgpack-python = "*"
numba = ">=0.61.2"
numpy = ">=2.2.6"
objgraph = "*"
pandas = ">=2.3.2"
prompt_toolkit = ">=3.0.39"
protobuf = ">=4.23.3"
psutil = ">=5.9.5"
ptpython = ">=3.0.26"
pydantic = ">=2"
pyjwt = ">=2.3.0"
pyperclip = ">=1.8.2"
pyyaml = ">=6.0"  # Note: environment.yml has yaml>=0.2.5 (C lib version); pyyaml is 6.x
requests = ">=2.31.0"
ruamel.yaml = ">=0.2.5"
rust = "*"
safe-pysha3 = "*"
scipy = ">=1.11.1"
six = ">=1.16.0"
solders = ">=0.19.0"
sqlalchemy = ">=1.4.49"
ta-lib = ">=0.6.4"
tabulate = "==0.9.0"
tqdm = ">=4.67.1"
ujson = ">=5.7.0"
urllib3 = ">=1.26.15,<2.0"
web3 = "*"
xrpl-py = "==4.4.0"
zlib = ">=1.2.13"
```

- [ ] **Step 3: Add pixi pypi dependencies**

Packages not on conda-forge (from `setup.py install_requires` + `environment.yml`, except `eip712-structs` from `pip_packages.txt`):

```toml
[tool.pixi.pypi-dependencies]
commlib-py = ">=0.11"
eip712-structs = "*"
pandas-ta = ">=0.4.71b"
scalecodec = "*"
```

- [ ] **Step 4: Add pixi features**

```toml
[tool.pixi.feature.dev.dependencies]
pytest = ">=7.4.0"
pytest-asyncio = ">=0.16.0"
pytest-cov = "*"
pytest-mock = "*"
coverage = ">=7.2.7"
diff-cover = ">=7.7.0"
ruff = "*"
mypy = "*"
pre-commit = ">=3.3.3"
cython-lint = "*"
autopep8 = "*"
flake8 = ">=6.0.0"

[tool.pixi.feature.ci.dependencies]
bandit = "*"
types-setuptools = "*"

[tool.pixi.feature.py310.dependencies]
python = "3.10.*"

[tool.pixi.feature.py311.dependencies]
python = "3.11.*"

[tool.pixi.feature.py312.dependencies]
python = "3.12.*"
```

Note: `flake8` and `autopep8` kept temporarily for backward compatibility. Remove after ruff migration is validated.

- [ ] **Step 5: Add pixi environments**

```toml
[tool.pixi.environments]
default = { features = ["dev"], solve-group = "default" }
ci = { features = ["ci", "dev"], solve-group = "default" }
py310 = { features = ["py310", "dev"], solve-group = "py310" }
py311 = { features = ["py311", "dev"], solve-group = "py311" }
py312 = { features = ["py312", "dev"], solve-group = "py312" }
```

- [ ] **Step 6: Add pixi tasks**

```toml
[tool.pixi.tasks]
install-dev = "pip install --no-build-isolation -e ."
build = { cmd = "python setup.py build_ext --inplace", depends-on = ["install-dev"] }
test = { cmd = "pytest test", depends-on = ["build"] }
test-unit = { cmd = "pytest test/hummingbot", depends-on = ["build"] }
lint = "ruff check hummingbot test"
lint-cython = "cython-lint hummingbot"
format = "ruff format hummingbot test"
format-check = "ruff format --check hummingbot test"
typecheck = "mypy hummingbot"
security = "bandit -c pyproject.toml -r hummingbot/"
quality = { depends-on = ["lint", "format-check"] }
check = { depends-on = ["quality", "test"] }
hooks-install = "pre-commit install"
submodule-update = "git submodule update --remote sub-packages/candles-feed"
```

- [ ] **Step 7: Checkpoint — `pixi install`**

```bash
pixi install
```

Expected: Environment resolves, `.pixi/` directory created, `pixi.lock` generated. If any package fails to resolve, move it to `[tool.pixi.pypi-dependencies]` and retry.

This is the critical checkpoint. Do NOT proceed until this passes. Debug dependency resolution issues here.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml pixi.lock
git commit -m "feat: add pixi workspace config with full dependency migration"
```

---

### Task 4: Tool Config Migration (ruff, coverage, cython-lint)

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `[tool.ruff]` sections**

Add after the existing `[tool.isort]` section:

```toml
[tool.ruff]
line-length = 120
target-version = "py310"
include = ["hummingbot/**/*.py", "test/**/*.py"]

[tool.ruff.lint]
select = ["E", "F", "W"]
ignore = ["E251", "E501", "E702", "W503", "W504"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]

[tool.cython-lint]
max-line-length = 120
```

These match the `.flake8` config: same line length (120), same ignores (E251, E501, E702, W503, W504). The `.flake8` per-file-ignores for `.pyx`/`.pxd` files (E225, E226) are intentionally omitted — ruff's `include` glob restricts to `.py` files; `cython-lint` handles Cython files separately.

- [ ] **Step 2: Replace `[tool.coverage.*]` sections**

Migrate the full `.coveragerc` content. Add after ruff:

```toml
[tool.coverage.run]
source_pkgs = ["hummingbot"]
branch = true
dynamic_context = "test_function"
omit = [
    "hummingbot/core/gateway/*",
    "hummingbot/core/management/*",
    "hummingbot/client/config/config_helpers.py",
    "hummingbot/client/config/conf_migration.py",
    "hummingbot/client/config/security.py",
    "hummingbot/client/hummingbot_application.py",
    "hummingbot/client/command/*",
    "hummingbot/client/settings.py",
    "hummingbot/client/ui/completer.py",
    "hummingbot/client/ui/layout.py",
    "hummingbot/client/tab/*",
    "hummingbot/client/ui/parser.py",
    "hummingbot/connector/derivative/position.py",
    "hummingbot/connector/derivative/dydx_v4_perpetual/*",
    "hummingbot/connector/derivative/dydx_v4_perpetual/data_sources/*",
    "hummingbot/connector/exchange/injective_v2/account_delegation_script.py",
    "hummingbot/connector/exchange/mexc/protobuf/*",
    "hummingbot/connector/exchange/paper_trade*",
    "hummingbot/connector/gateway/**",
    "hummingbot/connector/test_support/*",
    "hummingbot/core/utils/gateway_config_utils.py",
    "hummingbot/core/utils/kill_switch.py",
    "hummingbot/core/utils/wallet_setup.py",
    "hummingbot/connector/mock*",
    "hummingbot/strategy/*/start.py",
    "hummingbot/strategy/dev*",
    "hummingbot/user/user_balances.py",
    "hummingbot/connector/exchange/cube/cube_ws_protobufs/*",
    "hummingbot/connector/exchange/ndax/*",
    "hummingbot/strategy/amm_arb/*",
    "hummingbot/strategy_v2/backtesting/*",
]

[tool.coverage.report]
fail_under = 70
precision = 2
skip_empty = true
exclude_lines = [
    "@(abc\\.)?abstractmethod",
    "if TYPE_CHECKING:",
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "if 0:",
    "raise AssertionError",
    "raise NotImplementedError",
    "if settings.DEBUG",
    "except asyncio.exceptions.TimeoutError:",
]

[tool.coverage.html]
directory = "coverage_html_report"
show_contexts = true

[tool.coverage.xml]
output = "coverage.xml"
```

- [ ] **Step 3: Update `[tool.pytest.ini_options]`**

Replace the existing minimal section:

```toml
[tool.pytest.ini_options]
testpaths = ["test"]
python_files = ["test_*.py"]
asyncio_default_fixture_loop_scope = "function"
addopts = "--strict-markers"
```

- [ ] **Step 4: Checkpoint — lint**

```bash
pixi run lint
```

Expected: Ruff runs, produces same (or fewer) violations as current flake8. Zero new violations from the config migration.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: migrate ruff, coverage, and pytest config to pyproject.toml"
```

---

### Task 5: Strip setup.py

**Files:**
- Modify: `setup.py`

- [ ] **Step 1: Rewrite setup.py to Cython-only**

Replace the full `setup.py` content. **All build logic preserved** — only metadata and `install_requires` removed (now in pyproject.toml):

```python
import os
import subprocess
import sys

import numpy as np
from Cython.Build import cythonize
from setuptools import setup
from setuptools.command.build_ext import build_ext

is_posix = (os.name == "posix")


class BuildExt(build_ext):
    """Strip -Wstrict-prototypes (C-only flag invalid for C++)."""
    def build_extensions(self):
        if os.name != "nt" and "-Wstrict-prototypes" in self.compiler.compiler_so:
            self.compiler.compiler_so.remove("-Wstrict-prototypes")
        super().build_extensions()


def main():
    cpu_count = os.cpu_count() or 8

    # --- Platform-specific compile/link flags ---
    extra_compile_args = []
    extra_link_args = []
    if is_posix:
        os_name = subprocess.check_output("uname").decode("utf8")
        if "Darwin" in os_name:
            extra_compile_args.extend(["-stdlib=libc++", "-std=c++11"])
            extra_link_args.extend(["-stdlib=libc++", "-std=c++11"])
        else:
            extra_compile_args.append("-std=c++11")
            extra_link_args.append("-std=c++11")

    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        extra_compile_args.append("-O0")

    # --- Cython options ---
    cython_kwargs = {"language": "c++", "language_level": 3}
    if is_posix:
        cython_kwargs["nthreads"] = cpu_count

    compiler_directives = {"annotation_typing": False}
    if os.environ.get("WITHOUT_CYTHON_OPTIMIZATIONS"):
        compiler_directives.update({
            "optimize.use_switch": False,
            "optimize.unpack_method_calls": False,
        })

    if len(sys.argv) > 1 and sys.argv[1] == "build_ext" and is_posix:
        sys.argv.append(f"--parallel={cpu_count}")

    # --- Generate extensions & apply flags ---
    extensions = cythonize(
        ["hummingbot/**/*.pyx"],
        compiler_directives=compiler_directives,
        **cython_kwargs,
    )
    for ext in extensions:
        ext.extra_compile_args = extra_compile_args
        ext.extra_link_args = extra_link_args

    # --- Metadata in pyproject.toml [project]; only build config here ---
    package_data = {"hummingbot": ["core/cpp/*", "VERSION", "templates/*TEMPLATE.yml"]}
    if "DEV_MODE" in os.environ:
        package_data[""] = ["*.pxd", "*.pyx", "*.h"]
        package_data["hummingbot"].append("core/cpp/*.cpp")

    setup(
        ext_modules=extensions,
        include_dirs=[np.get_include()],
        package_data=package_data,
        cmdclass={"build_ext": BuildExt},
    )


if __name__ == "__main__":
    main()
```

What's removed: `name`, `version`, `description`, `author`, `url`, `license`, `packages`, `install_requires`, `scripts`, `find_packages`, `fnmatch` import.

What's preserved: `BuildExt`, C++ language mode, macOS/Linux flags, `WITHOUT_CYTHON_OPTIMIZATIONS`, `DEV_MODE`, parallel build, `annotation_typing: False`.

- [ ] **Step 2: Checkpoint — build**

```bash
pixi run build
```

Expected: All `.pyx` files compile. `pixi run python -c "import hummingbot"` succeeds.

- [ ] **Step 3: Commit**

```bash
git add setup.py
git commit -m "refactor: strip setup.py to Cython-only build (metadata in pyproject.toml)"
```

---

### Task 6: Pre-commit Migration

**Files:**
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Rewrite `.pre-commit-config.yaml`**

Replace the full file content:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
        exclude: '\.(pyx|pxd)$'
      - id: ruff-format
        exclude: '\.(pyx|pxd)$'
  - repo: https://github.com/MarcoGorelli/cython-lint
    rev: v0.16.0
    hooks:
      - id: cython-lint
  - repo: https://github.com/CoinAlpha/git-hooks
    rev: 78f0683233a09c68a072fd52740d32c0376d4f0f
    hooks:
      - id: detect-wallet-private-key
        types: [file]
        exclude: .json
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        files: "\\.(py)$"
        args: [--settings-path=pyproject.toml]
```

Changes from current:
- `pre-commit-hooks`: bumped from v2.3.0 to v4.5.0, removed `flake8` hook (replaced by ruff)
- Added `ruff-pre-commit` with `ruff` (lint+fix) and `ruff-format`
- Added `cython-lint` for `.pyx`/`.pxd` files
- Removed `autopep8` hook (ruff-format replaces it)
- Removed `eslint` hook (kept if JS files exist — check if needed)
- Kept `detect-wallet-private-key` and `isort` unchanged

- [ ] **Step 2: Reinstall hooks**

```bash
pixi run hooks-install
```

- [ ] **Step 3: Test hooks**

```bash
pixi run -- pre-commit run --all-files
```

Expected: All hooks pass. If ruff finds new violations not caught by flake8, either fix them or add to `ignore` list.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: migrate pre-commit from flake8/autopep8 to ruff/cython-lint"
```

---

### Task 7: Cleanup — Delete Migrated Files

**Files:**
- Delete: `.coveragerc`
- Delete: `.flake8`
- Delete: `setup/environment.yml`
- Delete: `setup/pip_packages.txt`

- [ ] **Step 1: Delete migrated config files**

```bash
git rm .coveragerc .flake8 setup/environment.yml setup/pip_packages.txt
```

- [ ] **Step 2: Verify nothing references deleted files**

Search for references to the deleted files in the codebase:

```bash
grep -r "environment.yml" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.yml" .
grep -r "\.coveragerc" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.yml" .
grep -r "\.flake8" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.yml" .
grep -r "pip_packages.txt" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.yml" .
```

If any references found (install scripts, Makefiles), update them to use pixi equivalents and `git add` the updated files. CI workflow references are out of scope (see Notes above).

- [ ] **Step 3: Commit**

`git rm` already stages deletions. Only use `git add` if Step 2 required additional file updates:

```bash
git commit -m "chore: remove migrated config files (coveragerc, flake8, environment.yml, pip_packages.txt)"
```

---

### Task 8: Full Validation

No file changes — validation only.

- [ ] **Step 1: Environment resolves**

```bash
pixi install
```

Expected: Clean install, no errors.

- [ ] **Step 2: Editable install**

```bash
pixi run install-dev
```

Expected: hummingbot installed in editable mode.

- [ ] **Step 3: Import check**

```bash
pixi run python -c "import hummingbot; print('hummingbot OK')"
```

- [ ] **Step 4: Cython build**

```bash
pixi run build
```

Expected: All `.pyx` files compile without errors.

- [ ] **Step 5: Workspace member — candles-feed**

```bash
pixi run python -c "from candles_feed.hb_compat import CandlesFactory; print('candles-feed OK')"
```

- [ ] **Step 6: Tests**

```bash
pixi run test
```

Compare pass/fail count with a run in the old conda environment.

- [ ] **Step 7: Lint**

```bash
pixi run lint
pixi run lint-cython
```

Expected: Zero new violations vs current baseline.

- [ ] **Step 8: Coverage**

```bash
pixi run -- pytest test --cov --cov-report=html
```

Expected: `coverage_html_report/` generated, `fail_under=70` enforced, `show_contexts=true` works.

- [ ] **Step 9: Pre-commit hooks**

```bash
pixi run -- pre-commit run --all-files
```

Expected: All hooks pass.

- [ ] **Step 10: Versioned environments (optional)**

```bash
pixi run -e py310 python --version
pixi run -e py311 python --version
pixi run -e py312 python --version
```

If `py312` fails to solve (likely `numba`), note in open issues.

---

### Task 9: Merge into bleeding-edge

- [ ] **Step 1: Final commit if any fixes from validation**

```bash
git add -A
git commit -m "fix: address validation issues from pixi migration"
```

- [ ] **Step 2: Add to branch-tracking.yaml**

The entry for `_for_bleed/pixi-workspace` should be added to `custom_git_setup/configs/branch-tracking.yaml` in the bleeding-edge-only patches section. Place it AFTER `_for_bleed/candles-public-api` (depends on it).

```yaml
      - name: _for_bleed/pixi-workspace
        enabled: true
        description: "Pixi workspace migration with candles-feed as workspace member"
        permanent: false
        disable_when_in_development: true
```

- [ ] **Step 3: Merge into bleeding-edge**

```bash
git checkout bleeding-edge
git merge _for_bleed/pixi-workspace
```

- [ ] **Step 4: Verify merge**

```bash
pixi install && pixi run build && pixi run test
```
