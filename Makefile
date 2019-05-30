.PHONY: test

test:
	nosetests -d -v -A 'not unstable' test/test*.py
