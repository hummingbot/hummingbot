global.options = {
  cachedHeader: true // inspect to see if something is served from cache
}

const zlib = require('zlib')
const { req, stExpect } = require('./common.js')
const { test } = require('tap')

test('does not gzip first response', (t) => {
  req('/test/st.js', { 'accept-encoding': 'none' }, (er, res, body) => {
    t.equal(res.statusCode, 200)
    t.notOk(res.headers['content-encoding'])
    t.notOk(res.headers['x-from-cache'])
    t.equal(body.toString(), stExpect)
    t.end()
  })
})

test('gzips second response', (t) => {
  req('/test/st.js', { 'accept-encoding': 'gzip' }, (er, res, body) => {
    t.error(er, 'no error')

    t.equal(res.statusCode, 200)
    t.equal(res.headers['content-encoding'], 'gzip')
    t.equal(res.headers['x-from-cache'], 'true')

    t.ok(body, 'returned a body')
    t.notEqual(body.toString(), stExpect, 'gzipped string')

    zlib.gunzip(body, (er, body) => {
      if (er) {
        throw er
      }
      t.equal(body.toString(), stExpect)
      t.end()
    })
  })
})
