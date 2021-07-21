const st = require('../st.js')
const { test } = require('tap')
const path = require('path')

const opts = Object.assign({
  autoindex: true,
  path: path.dirname(__dirname),
  url: '/test'
}, global.options || {})

const mount = st(opts)

test('call next() if asset not found', (t) => {
  const req = { url: '/does-not-exist?a=b' }
  t.plan(1)
  mount(req, req, () => t.equal(req.url, '/does-not-exist?a=b'))
})
