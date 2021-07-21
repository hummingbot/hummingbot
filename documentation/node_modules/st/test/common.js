const path = require('path')
const fs = require('fs')
const http = require('http')
const request = require('request')
const { test, tearDown } = require('tap')

const st = require('../st.js')

let address
let server

const opts = Object.assign({
  autoindex: true,
  path: path.dirname(__dirname),
  url: '/test'
}, global.options || {})

const stExpect = fs.readFileSync(require.resolve('../st.js'), 'utf8')
const mount = st(opts)

function req (url, headers, cb) {
  if (typeof headers === 'function') {
    cb = headers
    headers = {}
  }

  let host = address.address
  if (address.family === 'IPv6') {
    host = `[${host}]`
  }

  request({
    encoding: null,
    url: `http://${host}:${address.port}${url}`,
    headers: headers,
    followRedirect: false
  }, cb)
}

test('setup', (t) => {
  server = http.createServer((req, res) => {
    try {
      if (!mount(req, res)) {
        res.statusCode = 404
        return res.end(`Not a match: ${req.url}`)
      }
    } catch (e) {
      res.statusCode = 500
      console.error(e)
      return res.end(`Internal error: ${e.message}`)
    }
  }).listen(0, '127.0.0.1', () => {
    t.pass('listening')
    address = server.address()
    t.end()
  })
})

tearDown(() => {
  server.close()
})

module.exports.mount = mount
module.exports.req = req
module.exports.stExpect = stExpect
module.exports.opts = opts
