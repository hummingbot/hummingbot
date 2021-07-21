global.options = {
  cors: false
}

const { req } = require('./common')
const test = require('tap').test

test('without CORS headers', function (t) {
  req('/test/st.js', function (er, res) {
    t.error(er)
    t.notOk(res.headers['access-control-allow-origin'])
    t.end()
  })
})
