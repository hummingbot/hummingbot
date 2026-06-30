.ONESHELL:
.PHONY: test run run_coverage report_coverage development-diff-cover uninstall build install setup deploy down link-cli

DYDX ?= 0
ENV_FILE := setup/environment.yml
ifeq ($(DYDX),1)
  ENV_FILE := setup/environment_dydx.yml
endif

test:
	coverage run -m pytest \
 	--ignore="test/mock" \
 	--ignore="test/hummingbot/connector/exchange/ndax/" \
 	--ignore="test/hummingbot/connector/derivative/dydx_v4_perpetual/" \
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
	conda env remove -n hummingbot -y

install:
	@if ! command -v conda >/dev/null 2>&1; then \
		echo "Error: Conda is not found in PATH. Please install Conda or add it to your PATH."; \
		exit 1; \
	fi
	@mkdir -p logs
	@echo "Using env file: $(ENV_FILE)"
	@if conda env list | awk '{print $$1}' | grep -qx hummingbot; then \
		conda env update -n hummingbot -f "$(ENV_FILE)"; \
	else \
		conda env create -n hummingbot -f "$(ENV_FILE)"; \
	fi
	@if [ "$$(uname)" = "Darwin" ]; then \
		conda install -n hummingbot -y appnope; \
	fi
	@conda run -n hummingbot conda develop .
	@conda run -n hummingbot python -m pip install --no-deps -r setup/pip_packages.txt > logs/pip_install.log 2>&1
	@conda run -n hummingbot pre-commit install
	@if [ "$$(uname)" = "Linux" ] && command -v dpkg >/dev/null 2>&1; then \
		if ! dpkg -s build-essential >/dev/null 2>&1; then \
			echo "build-essential not found, installing..."; \
			sudo apt-get update && sudo apt-get upgrade -y && sudo apt-get install -y build-essential; \
		fi; \
	fi
	@conda run -n hummingbot --no-capture-output python setup.py build_ext --inplace
	@conda run -n hummingbot bash -c 'ln -sf "$(CURDIR)/bin/hbot" "$$CONDA_PREFIX/bin/hbot"'
	@echo "Done. Run: conda activate hummingbot && hbot --help"

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
	conda run -n hummingbot --no-capture-output ./bin/hummingbot_quickstart.py $(ARGS)

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
	@set -a; . ./.compose.env 2>/dev/null || true; set +a; \
	docker compose up -d

down:
	docker compose --profile gateway down
