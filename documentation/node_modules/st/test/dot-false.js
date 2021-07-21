global.dot = false

const { test } = require('tap')
const { req } = require('./dot-common')

// failing per https://github.com/isaacs/st/issues/67
test('non-dotted file', (t) => {
  req('/index.html', (er, res, body) => {
    t.equal(res.statusCode, 200)
    t.end()
  })
})

test('dotted file', (t) => {
  req('/.index.html', (er, res, body) => {
    t.equal(res.statusCode, 403)
    t.end()
  })
})
