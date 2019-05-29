.PHONY: test

test:
	nosetests -d -v -A 'stable' test/test*.py
