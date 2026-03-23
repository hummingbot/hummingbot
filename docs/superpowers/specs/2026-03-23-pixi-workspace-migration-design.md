# Hummingbot Pixi Workspace Migration Design

> **Date**: 2026-03-23
> **Branch**: `_for_bleed/candles-public-api` (prerequisite), new branch TBD for migration
> **Status**: Draft (rev 2 — post-review)
> **Minimum pixi version**: 0.40+ (workspace support with pyproject.toml members)

## Goal

Transform hummingbot into a pixi workspace project with candles-feed as a workspace member, enabling seamless development iteration and shared dependency resolution between the two packages.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cython compilation | Keep setuptools as build backend | Lowest risk; pixi manages env, setuptools handles Cython |
| Workspace topology | Hummingbot as workspace root, candles-feed as member | Tight dev iteration with shared solve; conda package for production |
| candles-feed inclusion | Git submodule at `sub-packages/candles-feed/` | Clean repo separation, pinned reference, independent release cycle |
| `dev/all-pyproject-environment` branch | Cherry-pick useful parts (ruff, coverage, cython-lint) | Branch is stale (older deps) but config migrations are real work |
| Dependency migration | One-shot to pixi sections | Clean break, single source of truth, no dual-system drift |
| Windows support | Not targeted | Current conda setup is Linux/macOS only; no Windows CI or contributors |

## Workspace Layout

```
hummingbot/                          # repo root = pixi workspace root
├── pyproject.toml                   # workspace config + project metadata + all tool config
├── pixi.lock                        # single lockfile (COMMITTED, not gitignored)
├── setup.py                         # Cython build (metadata stripped, build logic preserved)
├── .gitmodules                      # submodule reference
├── .gitattributes                   # pixi.lock as binary for diff
├── .pre-commit-config.yaml          # ruff + cython-lint (migrated from flake8/autopep8)
├── sub-packages/
│   └── candles-feed/                # git submodule → MementoRC/hb-candles-feed
│       └── pyproject.toml           # candles-feed's own pixi config (workspace member)
├── hummingbot/                      # main source
├── scripts/
├── controllers/
└── test/
```

## pyproject.toml Structure

### Build System (keep setuptools for Cython)

```toml
[build-system]
requires = ["setuptools", "wheel", "numpy>=2.2.6", "cython>=3.0.12"]
build-backend = "setuptools.build_meta"
```

### Project Metadata (migrate from setup.py)

```toml
[project]
name = "hummingbot"
version = "20260302"
description = "Hummingbot"
authors = [{name = "Hummingbot Foundation", email = "dev@hummingbot.org"}]
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
scripts = {hummingbot = "bin.hummingbot_quickstart:main"}

[tool.setuptools.packages.find]
include = ["hummingbot", "hummingbot.*"]
exclude = [
    "hummingbot.connector.gateway.clob_spot.data_sources.injective",
    "hummingbot.connector.gateway.clob_perp.data_sources.injective_perpetual",
]

[tool.setuptools.package-data]
hummingbot = ["core/cpp/*", "VERSION", "templates/*TEMPLATE.yml"]
```

### Pixi Workspace

```toml
[tool.pixi.workspace]
channels = ["conda-forge"]
platforms = ["linux-64", "osx-arm64"]
members = ["sub-packages/candles-feed"]
```

### Pixi Dependencies — Complete Enumeration

All packages from `setup/environment.yml` + `setup.py install_requires` + `setup/pip_packages.txt`, audited for conda-forge availability:

```toml
[tool.pixi.dependencies]
# --- Build/install ---
python = ">=3.10.12"
cython = ">=3.0.12"
setuptools = ">=80.8.0"
pip = ">=23.2.1"
# --- Core runtime (conda-forge) ---
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
pyyaml = ">=0.2.5"
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

[tool.pixi.pypi-dependencies]
# Packages requiring pip install (not on conda-forge or conda version problematic)
commlib-py = ">=0.11"
eip712-structs = "*"
pandas-ta = ">=0.4.71b"
scalecodec = "*"
```

**Notes on specific packages:**
- `rust`: Compiler toolchain needed by some deps that build from source (e.g., `solders`). Investigate if pre-built wheels eliminate this need.
- `injective-py`: Version spec fixed from invalid `>=1.12.*` to `>=1.12`
- `ptpython`: Version spec fixed from `>3.0.25` to `>=3.0.26`
- `urllib3`: Critical `<2.0` upper bound preserved (tests fail otherwise)
- `sqlalchemy`: Kept at `>=1.4.49` (not tightened to `>=2.0`) to match current constraint
- `commlib-py`: Moved to pypi-dependencies; exact pin `==0.11.5` relaxed to `>=0.11` — verify conda-forge availability before finalizing
- `pandas-ta`: Pre-release version; may need pypi for availability
- `conda-build`: Removed from runtime deps — build tool for conda packaging, not needed in dev env. Address separately in production packaging workflow.

### Pixi Features

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

**Note:** `flake8` and `autopep8` kept in dev feature during transition period for backward compatibility with existing pre-commit hooks. Remove once ruff migration is validated.

### Pixi Environments

```toml
[tool.pixi.environments]
default = { features = ["dev"], solve-group = "default" }
ci = { features = ["ci", "dev"], solve-group = "default" }
py310 = { features = ["py310", "dev"], solve-group = "py310" }
py311 = { features = ["py311", "dev"], solve-group = "py311" }
py312 = { features = ["py312", "dev"], solve-group = "py312" }
```

**Versioned environment risk:** `numba` has specific Python version support matrices. If `numba>=0.61.2` doesn't resolve under Python 3.12, the `py312` solve will fail. Validate each versioned environment independently.

### Pixi Tasks

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

**Note:** `install-dev` uses `pip install --no-build-isolation -e .` instead of deprecated `python setup.py` direct invocation for the editable install. The `build` task still calls `setup.py build_ext --inplace` for Cython compilation specifically, which remains supported for extension building.

### Tool Configuration

#### Ruff (replaces .flake8)

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

**Note:** `W503` and `W504` (line break before/after binary operator) preserved from `.flake8` to avoid new warnings on existing code.

#### Coverage (replaces .coveragerc — FULL migration)

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

#### Pytest

```toml
[tool.pytest.ini_options]
testpaths = ["test"]
python_files = ["test_*.py"]
asyncio_default_fixture_loop_scope = "function"
addopts = "--strict-markers"
```

#### Existing Tool Config

```toml
[tool.black]
# ... existing config unchanged

[tool.isort]
# ... existing config EXCEPT remove `conda_env = "hummingbot"` (meaningless in pixi)
```

## setup.py Reduction

Strip metadata (moves to `[project]`). **Preserve all build logic:**

```python
import fnmatch
import os
import subprocess
import sys

import numpy as np
from Cython.Build import cythonize
from setuptools import find_packages, setup
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

**Key preservations:** C++ language mode, platform-specific flags, `BuildExt` subclass, `WITHOUT_CYTHON_OPTIMIZATIONS`, `DEV_MODE`, parallel build, `annotation_typing: False`.

**Removed from setup.py** (now in pyproject.toml): `name`, `version`, `description`, `author`, `url`, `license`, `packages`, `install_requires`, `scripts`.

## .pre-commit-config.yaml Migration

Replace flake8/autopep8/isort hooks with ruff. Pin ruff version to match pixi-managed version:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0  # Keep aligned with pixi-managed ruff version
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
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key
```

## .gitattributes (new)

```
pixi.lock linguist-generated=true binary
```

## Files Deleted After Migration

| File | Replaced By |
|------|-------------|
| `setup/environment.yml` | `[tool.pixi.dependencies]` + `[tool.pixi.pypi-dependencies]` |
| `setup/pip_packages.txt` | `[tool.pixi.pypi-dependencies]` |
| `.coveragerc` | `[tool.coverage.*]` in pyproject.toml |
| `.flake8` | `[tool.ruff]` in pyproject.toml |

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Expanded with all sections above |
| `setup.py` | Metadata stripped, all build logic preserved |
| `.pre-commit-config.yaml` | flake8→ruff, add cython-lint |
| `.gitmodules` | New — candles-feed submodule |
| `.gitattributes` | New — pixi.lock as binary |
| `.gitignore` | Add `.pixi/` (NOT pixi.lock — that gets committed) |
| `[tool.isort]` | Remove `conda_env = "hummingbot"` |

## Migration Procedure (Sequenced)

### Phase 1: Foundation
1. Create branch `_for_bleed/pixi-workspace`
2. Add git submodule: `git submodule add <candles-feed-url> sub-packages/candles-feed`
3. Create `.gitattributes` with pixi.lock binary rule
4. Update `.gitignore`: add `.pixi/`, remove any pixi.lock exclusion

### Phase 2: pyproject.toml Expansion
5. Add `[project]` metadata section
6. Add `[tool.setuptools.*]` sections (packages.find, package-data)
7. Add `[tool.pixi.workspace]` with channels, platforms, members
8. Add `[tool.pixi.dependencies]` — full enumeration from environment.yml
9. Add `[tool.pixi.pypi-dependencies]` — pip-only packages
10. Add `[tool.pixi.feature.*]` sections (dev, ci, py310/311/312)
11. Add `[tool.pixi.environments]`
12. Add `[tool.pixi.tasks]`
13. **Checkpoint:** `pixi install` succeeds

### Phase 3: Tool Config Migration
14. Cherry-pick `[tool.ruff]` from dev/all-pyproject-environment (add W503/W504 ignores)
15. Migrate `.coveragerc` → `[tool.coverage.*]` (full content)
16. Add `[tool.cython-lint]`
17. Remove `conda_env` from `[tool.isort]`
18. **Checkpoint:** `pixi run lint` passes

### Phase 4: setup.py + Pre-commit
19. Strip setup.py to Cython-only (preserve all build logic)
20. Update `.pre-commit-config.yaml` (ruff + cython-lint)
21. **Checkpoint:** `pixi run build` compiles, `pixi run python -c "import hummingbot"` works

### Phase 5: Cleanup + Validation
22. Delete `setup/environment.yml`, `setup/pip_packages.txt`, `.coveragerc`, `.flake8`
23. Run full validation suite (see below)
24. Commit and merge into bleeding-edge

## Validation Strategy

After migration, validate:

1. **Environment**: `pixi install` succeeds, resolves all deps
2. **Editable install**: `pixi run install-dev` completes
3. **Import**: `pixi run python -c "import hummingbot"` works
4. **Build**: `pixi run build` compiles all `.pyx` files
5. **Tests**: `pixi run test` passes same tests as current conda env
6. **Workspace member**: `pixi run python -c "from candles_feed.hb_compat import CandlesFactory"` resolves
7. **Lint**: `pixi run lint` and `pixi run lint-cython` pass with zero new violations
8. **Coverage**: `pixi run pytest --cov` produces same coverage report structure
9. **Pre-commit**: `pixi run hooks-install && git commit --allow-empty -m test` runs hooks correctly
10. **Versioned envs**: `pixi run -e py310 python --version` (repeat for py311, py312) — validate numba resolves

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Conda-forge missing packages (esp. osx-arm64) | Full audit before Phase 2; use pypi-dependencies as escape hatch |
| Cython C++ build breaks under pixi env | setup.py preserves all platform flags, BuildExt, compiler directives |
| Workspace solve conflicts with candles-feed | Shared solve-group; candles-feed has minimal deps (aiohttp, numpy, pandas) |
| Pre-commit hooks run outside pixi env | Document `pixi run hooks-install`; add activation script |
| `pixi.lock` merge conflicts | `.gitattributes` binary rule; regenerate with `pixi install` |
| `numba` blocks py312 solve | Test each versioned env; pin numba version or exclude from py312 |
| `rust` compiler dep unclear | Investigate which dep needs it (likely `solders`); may be removable if pre-built wheels used |
| Submodule pin drift | `pixi run submodule-update` task; document in developer workflow |
| `urllib3>=2.0` breaks tests | Constraint `<2.0` explicitly preserved in pixi deps |
| `setup.py` direct invocation deprecated | `install-dev` task uses `pip install -e .`; only `build_ext` uses setup.py directly |

## Production Path

- **Development**: Pixi workspace with candles-feed as submodule member (editable install via `pixi run install-dev`)
- **Production**: Hummingbot depends on `hb-candles-feed` conda package from conda-forge (or private channel). The `try/except` import fallback in `market_data_provider.py` (already merged) handles both modes.
- **Conda packaging**: `conda-build` is NOT a runtime dependency. Building hummingbot as a conda package uses a separate feedstock with its own build environment, not the dev pixi environment.

## Relationship to Existing Work

- **Prerequisite**: `_for_bleed/candles-public-api` branch (merged into bleeding-edge) — provides the public API on CandlesBase and the hb-candles-feed import fallback in MarketDataProvider
- **Reference**: `dev/all-pyproject-environment` branch — cherry-pick ruff/coverage/cython-lint config
- **Reference**: candles-feed's `pyproject.toml` — template for pixi workspace patterns (features, environments, solve-groups, tasks)

## Open Questions

1. **`rust` compiler dependency**: Which package requires building from source? Can pre-built wheels replace it?
2. **`commlib-py` conda-forge availability**: Currently pinned `==0.11.5` in environment.yml. If not on conda-forge, stays in pypi-dependencies.
3. **`pandas-ta` pre-release**: `>=0.4.71b` is a pre-release spec. Verify conda-forge has this version or keep in pypi-dependencies.
4. **CI pipeline updates**: GitHub Actions workflows need updating to use `pixi run` commands — scope TBD based on current CI setup.
