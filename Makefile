.ONESHELL:
.PHONY: test
.PHONY: run_coverage
.PHONY: report_coverage
.PHONY: development-diff-cover
.PHONY: docker
.PHONY: install
.PHONY: uninstall
.PHONY: clean
.PHONY: build
.PHONY: run-v2

test:
	coverage run -m pytest \
 	--ignore="test/mock" \
 	--ignore="test/hummingbot/connector/derivative/dydx_v4_perpetual/" \
 	--ignore="test/hummingbot/remote_iface/" \
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

docker:
	git clean -xdf && make clean && docker build -t hummingbot/hummingbot${TAG} -f Dockerfile .

clean:
	./clean

install:
	./install

uninstall:
	./uninstall

build:
	./compile

run-v2:
	./bin/hummingbot_quickstart.py -p a -f v2_with_controllers.py -c $(filter-out $@,$(MAKECMDGOALS))

%:
	@:
