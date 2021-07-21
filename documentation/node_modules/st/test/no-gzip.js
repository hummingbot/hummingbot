// turn off gzip compression
global.options = {
  gzip: false
}

const { test } = require('tap')
const { req, stExpect } = require('./basic.js')

// additional test to ensure that it's actually not gzipping

test('does not gzip the response', (t) => {
  req('/test/st.js', { 'accept-encoding': 'gzip' }, (er, res, body) => {
    t.equal(res.statusCode, 200)
    t.notOk(res.headers['content-encoding'])
    t.equal(body.toString(), stExpect)
    t.end()
  })
})
