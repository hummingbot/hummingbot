'use strict'

module.exports = whitespace

var fromCharCode = String.fromCharCode
var ws = /\s/

function whitespace(code) {
  return ws.test(fromCharCode(code))
}
