.ONESHELL:
.PHONY: test run run_coverage report_coverage development-diff-cover uninstall build install setup deploy down link-cli gateway-models

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

# Header stamped onto the generated models. `#` starts a comment in a Makefile, so it
# has to reach the recipe through a variable.
HASH := \#
define GATEWAY_MODELS_HEADER
$(HASH) Generated from gateway-openapi.json by 'make gateway-models'. Do not edit.
$(HASH) flake8: noqa: E501
endef
export GATEWAY_MODELS_HEADER

# Regenerate hummingbot/core/gateway/gateway_models.py from the vendored Gateway spec.
# Adopting a Gateway change is two steps — refresh the spec, then rerun this:
#   cd ../gateway && pnpm generate:openapi && cp openapi.json ../hummingbot/gateway-openapi.json
#   make gateway-models
# The target Python is setup.py's python_requires floor, not the interpreter you happen
# to be on: 3.12 would emit StrEnum, which 3.10 does not have.
#
# --ignore-enum-constraints keeps `connector` and `network` as plain strings. Gateway
# constrains them by enum so its docs can offer dropdowns, but generating those as Python
# enums would bake a connector and network roster into this client: a venue Gateway added
# after the last spec refresh would be rejected here before the request left the process.
# It also removes the only classes the generator had to number (Connector9, Connector15,
# ...), which were renamed by any unrelated route insertion.
#
# test_gateway_models_match_spec.py fails if the committed models drift from the spec.
gateway-models:
	python -m datamodel_code_generator \
		--input gateway-openapi.json --input-file-type openapi --openapi-scopes schemas \
		--output hummingbot/core/gateway/gateway_models.py --output-model-type pydantic_v2.BaseModel \
		--snake-case-field --target-python-version 3.10 --disable-timestamp \
		--ignore-enum-constraints \
		--formatters black --formatters isort \
		--custom-file-header "$$GATEWAY_MODELS_HEADER"

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
	@if [ -f ./.compose.env ]; then set -a; . ./.compose.env; set +a; fi; \
	docker compose up -d

down:
	docker compose --profile gateway down
