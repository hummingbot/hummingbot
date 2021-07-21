'use strict'

module.exports = serializeFormattedCode

var fromCharCode = String.fromCharCode

var graveAccent = 96 // '`'

function serializeFormattedCode(code) {
  return '`' + (code === graveAccent ? '` ` `' : fromCharCode(code)) + '`'
}
