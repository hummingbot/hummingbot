const st = require('../st.js')
const test = require('tap').test
const port = process.env.PORT || 1337
const path = require('path')
const request = require('request')
const assert = require('assert')
const fs = require('fs')
const http = require('http')

let middlewareServer
let server

// mount the dirname on the /test url
const mount1 = st({
  autoindex: true,
  path: path.dirname(__dirname),
  url: '/test',
  cache: {
    fd: {
      max: 3
    }
  }
})

// mount the test dir on the /blerg url
const mount2 = st({
  autoindex: true,
  path: __dirname,
  url: '/blerg',
  cache: {
    fd: {
      max: 3
    }
  }
})

function req (url, headers, cb) {
  if (typeof headers === 'function') {
    cb = headers
    headers = {}
  }

  let reqs = 0
  let errState = null
  let prev = null

  request({
    encoding: null,
    url: `http://localhost:${port}${url}`,
    headers: headers,
    agentOptions: { maxSockets: 50 }
  }, next)
  request({
    encoding: null,
    url: `http://localhost:${(port + 1)}${url}`,
    headers: headers,
    agentOptions: { maxSockets: 50 }
  }, next)

  function next (er, res, body) {
    if (errState) {
      return
    }
    if (er) {
      errState = er
      return cb(er, res, body)
    }
    if (++reqs === 2) {
      assert.strictEqual(res.statusCode, prev.res.statusCode)
      // compare dates, they should be approximately the same
      assert(Math.abs(new Date(res.headers.date).getTime() -
                      new Date(res.headers.date).getTime()) < 1000)
      // compare the headers minus the 'date' value
      res.headers.date = prev.res.headers.date = null
      assert.deepStrictEqual(res.headers, prev.res.headers)
      assert.strictEqual(`${body}`, `${prev.body}`)
      return cb(er, res, body)
    }
    prev = { res: res, body: body }
  }
}

test('setup middleware server', function (t) {
  // using the middleware approach
  middlewareServer = http.createServer(function (req, res) {
    mount1(req, res, function () {
      mount2(req, res, function () {
        res.statusCode = 404
        return res.end(`Not a match: ${req.url}`)
      })
    })
  })
  middlewareServer.listen(port, '127.0.0.1', function () {
    t.pass('listening')
    t.end()
  })
})

test('setup regular server', function (t) {
  server = http.createServer(function (req, res) {
    if (!mount1(req, res) && !mount2(req, res)) {
      res.statusCode = 404
      return res.end(`Not a match: ${req.url}`)
    }
  })
  server.listen(port + 1, '127.0.0.1', function () {
    t.pass('listening')
    t.end()
  })
})

let stEtag
const stExpect = fs.readFileSync(require.resolve('../st.js')).toString()

test('/test/st.js', function (t) {
  req('/test/st.js', function (er, res, body) {
    t.equal(res.statusCode, 200)
    t.ok(res.headers.etag)
    stEtag = res.headers.etag
    t.equal(body.toString(), stExpect)
    t.end()
  })
})

test('/test/st.js 304', function (t) {
  req('/test/st.js', { 'if-none-match': stEtag }, function (er, res, body) {
    t.equal(res.statusCode, 304)
    t.equal(body.length, 0)
    t.end()
  })
})

let mmEtag
const mmExpect = fs.readFileSync(__filename, 'utf8')
test('/blerg/multi-mount.js', function (t) {
  req('/blerg/multi-mount.js', function (er, res, body) {
    t.equal(res.statusCode, 200)
    t.ok(res.headers.etag)
    mmEtag = res.headers.etag
    t.equal(body.toString(), mmExpect)
    t.end()
  })
})

test('/test/test/multi-mount.js', function (t) {
  req('/test/test/multi-mount.js', function (er, res, body) {
    t.equal(res.statusCode, 200)
    t.equal(mmEtag, res.headers.etag)
    t.equal(body.toString(), mmExpect)
    t.end()
  })
})

let rmEtag
const rmExpect = fs.readFileSync(path.resolve(__dirname, '../README.md'), 'utf8')
let pjEtag
const pjExpect = fs.readFileSync(path.resolve(__dirname, '../package.json'), 'utf8')
let idEtag
const idExpect = fs.readFileSync(path.join(__dirname, '/fixtures/index.html'), 'utf8')
test('just get a few more etags', function (t) {
  let n = 3

  req('/test/package.json', function (er, res, body) {
    if (er) {
      throw er
    }
    t.equal(body.toString(), pjExpect)
    pjEtag = res.headers.etag
    if (--n === 0) {
      t.end()
    }
  })

  req('/test/README.md', function (er, res, body) {
    if (er) {
      throw er
    }
    t.equal(body.toString(), rmExpect)
    rmEtag = res.headers.etag
    if (--n === 0) {
      t.end()
    }
  })

  req('/test/test/fixtures/index.html', function (er, res, body) {
    if (er) {
      throw er
    }
    t.equal(body.toString(), idExpect)
    idEtag = res.headers.etag
    if (--n === 0) {
      t.end()
    }
  })
})

test('many parallel requests', function (t) {
  const n = 50
  const reqs =
    [['/test/test/multi-mount.js', mmEtag, mmExpect],
      ['/blerg/multi-mount.js', mmEtag, mmExpect],
      ['/test/st.js', stEtag, stExpect],
      ['/test/README.md', rmEtag, rmExpect],
      ['/test/package.json', pjEtag, pjExpect],
      ['/test/test/fixtures/index.html', idEtag, idExpect],
      ['/blerg/fixtures/index.html', idEtag, idExpect]]

  let total = n * reqs.length

  for (let i = 0; i < n; i++) {
    reqs.forEach(function (r) {
      req(r[0], next(r))
    })
  }

  function next (r) {
    return (er, res, body) => {
      if (er) {
        console.error('problem with', r[0])
        throw er
      }

      t.pass(r[0])
      t.ok(res)
      t.ok(res.headers)
      t.equal(res.headers.etag, r[1])
      t.equal(body.toString(), r[2].toString())

      if (--total === 0) {
        process.nextTick(() => {
          t.ok(require('fd')._totalOpenFds <= 6) // max of 3 fds per mount
          t.end()
        })
      }
    }
  }
})

test('shutdown regular server', (t) => {
  server.close(() => {
    t.pass('closed')
    t.end()
  })
})

test('shutdown middleware server', (t) => {
  middlewareServer.close(() => {
    t.pass('closed')
    t.end()
  })
})
