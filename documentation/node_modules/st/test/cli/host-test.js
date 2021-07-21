const os = require('os')
let { test, fail, comment } = require('tap')
const { serve } = require('./common')
const port = 1338

const otherAddress = (() => {
  const ifaces = os.networkInterfaces()
  for (const iface in ifaces) {
    const addrs = ifaces[iface]
    for (let i = 0; i < addrs.length; ++i) {
      const addr = addrs[i].address
      if (/^127\./.test(addr) || /^::1$/.test(addr)) { // loopback device
        continue
      }
      if (/^fe80:/.test(addr)) { // link-local address
        continue
      }
      return addr
    }
  }
  return null
})()
if (!otherAddress) {
  fail('No non-loopback network address found', { skip: true })
  test = () => {}
} else {
  comment('Using ' + otherAddress + ' as non-localhost address')
}

function addr2url (addr, path) {
  if (/:/.test(addr)) {
    addr = '[' + addr + ']'
  }
  addr = 'http://' + addr + ':' + port
  if (path) {
    addr += path
  }
  return addr
}

function testServer (name, args, addr, canConnect, cannotConnect) {
  test(name, (t) => {
    serve(args.concat(['--port', port]), (req) => {
      canConnect.forEach(checkConnections(t, req, true))
      cannotConnect.forEach(checkConnections(t, req, false))
    }, (err, stdout, stderr) => {
      t.ifError(err)
      t.equal(stderr, '')
      if (addr) {
        t.equal(stdout, 'listening at ' + addr2url(addr) + '\n')
      }
      t.end()
    })
  })
}

function checkConnections (t, req, canConnect) {
  return (addr) => {
    const url = addr2url(addr, '/st.js')
    req(url, (er, res, body) => {
      if (canConnect) {
        t.ifError(er, url) && t.equal(res.statusCode, 200, url)
      } else {
        t.ok(er, url)
      }
    })
  }
}

testServer(
  'Listening on all ports by default',
  [], null,
  ['127.0.0.1', 'localhost', otherAddress], []
)

testServer(
  'Restricted to localhost',
  ['--localhost'], 'localhost',
  ['127.0.0.1', 'localhost'], [otherAddress]
)

testServer(
  'Restricted to non-local host',
  ['--host', otherAddress], otherAddress,
  [otherAddress], ['127.0.0.1']
)

testServer(
  'Restricted to IPv4',
  ['--host', '127.0.0.1'], '127.0.0.1',
  ['127.0.0.1'], ['::1']
)
