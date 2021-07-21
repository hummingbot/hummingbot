'use strict'

module.exports = serializeCharCode

function serializeCharCode(code) {
  return 'U+' + code.toString(16).toUpperCase().padStart(4, '0')
}
