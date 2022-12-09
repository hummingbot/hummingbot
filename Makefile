.ONESHELL:
.PHONY: test
.PHONY: run_coverage
.PHONY: report_coverage
.PHONY: development-diff-cover

test:
	coverage run -m nose --exclude-dir="test/connector" --exclude-dir="test/debug" --exclude-dir="test/mock" --exclude-dir="test/hummingbot/connector/gateway"

run_coverage: test
	coverage report
	coverage html

report_coverage:
	coverage report
	coverage html

development-diff-cover:
	coverage xml
	diff-cover --compare-branch=origin/development coverage.xml
