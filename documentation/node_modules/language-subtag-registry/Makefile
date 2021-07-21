REGISTRY_CACHE := scripts/cache/language-subtag-registry

update:
	curl http://www.iana.org/assignments/language-subtag-registry/language-subtag-registry \
		--header "Accept-Charset: utf-8" \
		--compressed \
		--output $(REGISTRY_CACHE)
	node scripts/importer $(REGISTRY_CACHE) data/json

test:
	find ./data/json/*.json -exec ./node_modules/.bin/jsonlint -q {} \;

.PHONY: update test
