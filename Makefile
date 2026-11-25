.ONESHELL:
.PHONY: test run run_coverage report_coverage development-diff-cover uninstall build install setup deploy down link-cli

DYDX ?= 0
INJECTIVE ?= 0
UV_EXTRA :=
ifeq ($(DYDX),1)
  UV_EXTRA += --extra dydx
endif
ifeq ($(INJECTIVE),1)
  UV_EXTRA += --extra injective
endif

test:
	coverage run -m pytest \
 	--ignore="test/mock" \
 	--ignore="test/hummingbot/connector/exchange/ndax/" \
 	--ignore="test/hummingbot/connector/derivative/dydx_v4_perpetual/" \
 	--ignore="test/hummingbot/connector/exchange/injective_v2/" \
 	--ignore="test/hummingbot/connector/derivative/injective_v2_perpetual/" \
 	--ignore="test/connector/utilities/oms_connector/" \
 	--ignore="test/hummingbot/strategy/amm_arb/" \
 	--ignore="test/hummingbot/strategy/cross_exchange_market_making/" \

run_coverage: test
	coverage report
	coverage html

report_coverage:
	coverage report
	coverage html

development-diff-cover:
	coverage xml
	diff-cover --compare-branch=origin/development coverage.xml

build:
	git clean -xdf && make clean && docker build -t hummingbot/hummingbot${TAG} -f Dockerfile .


uninstall:
	rm -rf .venv

install:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Error: uv is not found in PATH. Please install uv: https://docs.astral.sh/uv/getting-started/installation/"; \
		exit 1; \
	fi
	@mkdir -p logs
	@uv sync $(UV_EXTRA) || { echo "Error: uv sync failed; the environment was not installed." >&2; exit 1; }
# Make `hummingbot` importable from any directory (replaces `conda develop .`).
# `uv sync` does not remove this file, but it is lost if the venv is recreated -- re-run `make install` then.
	@site_packages="$$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")" && \
		[ -d "$$site_packages" ] && \
		printf '%s\n' "$(CURDIR)" > "$$site_packages/hummingbot-dev.pth" || \
		echo "Warning: could not write hummingbot-dev.pth; 'import hummingbot' will only work from the repo root."
	@if [ "$$(uname)" = "Linux" ] && command -v dpkg >/dev/null 2>&1; then \
		if ! dpkg -s build-essential >/dev/null 2>&1; then \
			echo "build-essential not found, installing..."; \
			sudo apt-get update && sudo apt-get upgrade -y && sudo apt-get install -y build-essential; \
		fi; \
	fi
	@uv run $(UV_EXTRA) python setup.py build_ext --inplace || { echo "Error: Cython build failed." >&2; exit 1; }
# Not fatal: fails when this is not a usable git checkout (e.g. a source tarball).
	@uv run $(UV_EXTRA) pre-commit install || echo "Warning: 'pre-commit install' failed; git hooks were not installed."
	@ln -sf "$(CURDIR)/bin/hbot" ".venv/bin/hbot"
	@echo "Done. Run: source .venv/bin/activate && hbot --help"

link-cli:
	@src="$(CURDIR)/bin/hbot-host"; dir="$${HBOT_BIN:-}"; \
	if [ -z "$$dir" ]; then \
		for d in /usr/local/bin "$$HOME/.local/bin"; do \
			if [ -w "$$d" ] || { [ ! -e "$$d" ] && mkdir -p "$$d" 2>/dev/null; }; then dir="$$d"; break; fi; \
		done; \
	fi; \
	if [ -z "$$dir" ]; then \
		echo "No writable bin dir found (tried /usr/local/bin, ~/.local/bin)."; \
		echo "Set HBOT_BIN to a writable dir on your PATH and retry, e.g.  make link-cli HBOT_BIN=\$$HOME/.local/bin"; \
		exit 1; \
	fi; \
	mkdir -p "$$dir"; ln -sf "$$src" "$$dir/hbot"; \
	echo "Linked $$dir/hbot -> bin/hbot-host"; \
	case ":$$PATH:" in *":$$dir:"*) ;; *) echo "NOTE: add $$dir to your PATH to run 'hbot'." ;; esac; \
	echo "Now 'hbot <command>' dispatches to your source env or the docker container."

run:
	uv run $(UV_EXTRA) ./bin/hummingbot_quickstart.py $(ARGS)

setup:
	@read -r -p "Include Gateway? [y/N] " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		echo "COMPOSE_PROFILES=gateway" > .compose.env; \
		echo "Gateway will be included."; \
	else \
		echo "COMPOSE_PROFILES=" > .compose.env; \
		echo "Gateway will NOT be included."; \
	fi

deploy:
	@if [ -f ./.compose.env ]; then set -a; . ./.compose.env; set +a; fi; \
	docker compose up -d

down:
	docker compose --profile gateway down
