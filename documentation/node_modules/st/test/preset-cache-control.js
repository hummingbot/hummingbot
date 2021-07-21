const st = require('../st.js')
const { test, tearDown } = require('tap')
const path = require('path')
const http = require('http')
const request = require('request')
const port = process.env.PORT || 1337

const opts = Object.assign({
  index: false,
  path: path.dirname(__dirname),
  url: '/test'
}, global.options || {})

const mount = st(opts)
let server
let cacheControl = null

function req (url, headers, cb) {
  if (typeof headers === 'function') {
    cb = headers
    headers = {}
  }
  request({
    encoding: null,
    url: 'http://localhost:' + port + url,
    headers: headers
  }, cb)
}

test('setup', (t) => {
  server = http.createServer((req, res) => {
    if (cacheControl) {
      res.setHeader('cache-control', cacheControl)
    }
    if (!mount(req, res)) {
      res.statusCode = 404
      return res.end('Not a match: ' + req.url)
    }
  }).listen(port, () => {
    t.pass('listening')
    t.end()
  })
})

tearDown(() => {
  server.close()
})

test('simple request', (t) => {
  cacheControl = null
  req('/test/st.js', (er, res, body) => {
    t.error(er)
    t.equal(res.headers['cache-control'], 'public, max-age=600')
    t.end()
  })
})

test('pre-set cache-control', (t) => {
  cacheControl = 'I\'m so excited, and I just can\'t hide it'
  req('/test/st.js', (er, res, body) => {
    t.error(er)
    t.equal(res.headers['cache-control'], cacheControl)
    t.end()
  })
})
