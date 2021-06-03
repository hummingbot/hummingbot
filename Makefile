.PHONY: test

.ONESHELL:

test:
	find test/hummingbot/ -iname "test_*.py" | xargs nosetests -v -d

coverage:
	find test/hummingbot/ -iname "test_*.py" | xargs nosetests -v -d --with-coverage --cover-inclusive --cover-package=hummingbot --cover-xml --cover-html
