.PHONY: test

test:
	nosetests -A 'stable' test/test*.py
