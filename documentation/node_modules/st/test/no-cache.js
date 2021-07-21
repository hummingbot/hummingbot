// turn off ALL caching.
global.options = {
  cache: false
}

// otherwise just the same as basic.
const { mount } = require('./basic.js')
const { test } = require('tap')

// additional tests to ensure that it's actually not caching.

test('all caches should be empty', (t) => {
  t.same(mount._this.cache.fd._cache.dump(), [])
  t.same(mount._this.cache.stat._cache.dump(), [])
  t.same(mount._this.cache.index._cache.dump(), [])
  t.same(mount._this.cache.readdir._cache.dump(), [])
  t.same(mount._this.cache.content._cache.dump(), [])
  t.end()
})
