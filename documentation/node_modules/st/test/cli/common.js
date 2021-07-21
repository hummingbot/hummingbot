'use strict'

const path = require('path')
const fs = require('fs')
const request = require('request')
const childProcess = require('child_process')
const bl = require('bl')

const port = process.env.PORT || 1337

const stExpect = fs.readFileSync(require.resolve('../../st.js'), 'utf8')

// Run server with given command line arguments,
// then allow cbRequests to schedule a bunch of requests,
// finally call cbDone.
// cbRequests gets the req function as an argument.

function serve (args, cbRequests, cbDone) {
  args = [require.resolve('../../bin/server.js')].concat(args || [])
  const server = childProcess.spawn(process.execPath, args, {
    cwd: path.dirname(path.dirname(__dirname)),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { LANG: 'C', LC_ALL: 'C' }
  })
  const stdout = bl()
  const stderr = bl()
  server.stdout.pipe(stdout)
  server.stderr.pipe(stderr)
  let thingsToDo = 4 // cbRequests, exit, stdout, stderr
  let code = null
  let signal = null
  let cbReqEr = null
  let outputSeen = false
  server.once('error', (er) => {
    thingsToDo = -10 // only call cbDone once
    cbDone(er)
  })
  server.once('exit', (c, s) => {
    code = c
    signal = s
    if (!outputSeen) {
      outputSeen = true
      --thingsToDo
    }
    then()
  })
  stdout.once('finish', then)
  stderr.once('finish', then)
  server.stdout.once('data', () => {
    if (outputSeen) return
    outputSeen = true
    try {
      cbRequests(req)
    } catch (er) {
      cbReqEr = er
    } finally {
      then()
    }
  })

  function then () {
    --thingsToDo
    if (thingsToDo === 3) { // all requests done, one way or another
      server.kill()
    } else if (thingsToDo === 0) {
      let er = null
      if (cbReqEr) {
        er = cbReqEr
      } else if (signal !== null && signal !== 'SIGTERM') {
        er = Error('Terminated by signal ' + signal)
      } else if (code !== null && code !== 0) {
        er = Error('Exited with code ' + code)
      }
      const o = stdout.toString(); const e = stderr.toString()
      if (er) {
        console.info(o)
        console.error(e)
      }
      cbDone(er, o, e)
    }
  }

  function req (url, headers, cb) {
    if (typeof headers === 'function') {
      cb = headers
      headers = {}
    }
    if (!/:\/\//.test(url)) {
      url = 'http://localhost:' + port + url
    }
    ++thingsToDo
    request({
      encoding: null,
      url: url,
      headers: headers
    }, (...args) => {
      try {
        cb.apply(null, args)
      } finally {
        then()
      }
    })
  }
}

module.exports.port = port
module.exports.stExpect = stExpect
module.exports.serve = serve
