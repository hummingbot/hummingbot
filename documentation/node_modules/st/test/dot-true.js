global.dot = true

const { test } = require('tap')
const { req } = require('./dot-common')

test('non-dotted file', (t) => {
  req('/index.html', (er, res, body) => {
    t.error(er)
    t.equal(res.statusCode, 200)
    t.end()
  })
})

test('dotted file', (t) => {
  req('/.index.html', (er, res, body) => {
    t.error(er)
    t.equal(res.statusCode, 200)
    t.end()
  })
})
