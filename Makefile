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

test:
	coverage run -m pytest \
 	--ignore="test/mock" \
 	--ignore="test/hummingbot/connector/gateway/amm" \
 	--ignore="test/hummingbot/connector/exchange/coinbase_advanced_trade" \
 	--ignore="test/hummingbot/connector/exchange/ndax" \
 	--ignore="test/hummingbot/connector/exchange/foxbit" \
 	--ignore="test/hummingbot/connector/derivative/dydx_v4_perpetual" \
 	--ignore="test/hummingbot/core/gateway" \

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
