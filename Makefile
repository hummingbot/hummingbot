.ONESHELL:
.PHONY: test
.PHONY: coverage
.PHONY: development-diff-cover

test:
	find test/hummingbot/ -iname "test_*.py" | xargs nosetests -v -d

coverage:
	find test/hummingbot/ -iname "test_*.py" | xargs nosetests -v -d --with-coverage --cover-inclusive --cover-package=hummingbot --cover-xml --cover-html

development-diff-cover:
	diff-cover --compare-branch=origin/development coverage.xml