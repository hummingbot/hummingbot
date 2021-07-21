const path = require('path')
const http = require('http')
const request = require('request')
const { test, tearDown } = require('tap')

const st = require('../st.js')

let address
let server

const opts = {
  dot: global.dot,
  path: path.join(__dirname, 'fixtures', '.dotted-dir')
}

const mount = st(opts)

const req = (url, cb) => {
  let host = address.address
  if (address.family === 'IPv6') {
    host = `[${host}]`
  }

  request({ url: `http://${host}:${address.port}${url}` }, cb)
}

test('setup', (t) => {
  server = http.createServer((req, res) => {
    if (!mount(req, res)) {
      res.statusCode = 404
      return res.end(`Not a match: ${req.url}`)
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

module.exports.req = req
