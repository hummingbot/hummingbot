global.options = {
  cors: true
}

const { test } = require('tap')
const { req } = require('./common')

test('CORS headers', (t) => {
  req('/test/st.js', (er, res) => {
    t.equal(res.headers['access-control-allow-origin'], '*')
    const headers = res.headers['access-control-allow-headers']
    t.ok(/Origin/.test(headers))
    t.ok(/X-Requested-With/.test(headers))
    t.ok(/Content-Type/.test(headers))
    t.ok(/Accept/.test(headers))
    t.ok(/Range/.test(headers))
    t.end()
  })
})
