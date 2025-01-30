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
	coverage run -m nose \
 	--exclude-dir="test/mock" \
 	--exclude-dir="test/hummingbot/connector/gateway/amm" \
 	--exclude-dir="test/hummingbot/connector/exchange/coinbase_advanced_trade" \
 	--exclude-dir="test/hummingbot/connector/exchange/ndax" \
 	--exclude-dir="test/hummingbot/connector/exchange/foxbit" \
 	--exclude-dir="test/hummingbot/connector/derivative/dydx_v4_perpetual" \
 	--exclude-dir="test/hummingbot/core/gateway" \

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
