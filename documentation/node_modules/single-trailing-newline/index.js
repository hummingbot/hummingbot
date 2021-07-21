'use strict'

var detectNewline = require('detect-newline')

module.exports = function singleTrailingNewline (str) {
  if (typeof str !== 'string') {
    throw new TypeError('single-trailing-newline expected a string')
  }


  var newlineChar = detectNewline(str)
  var trimmedStr = str.replace(/(\r?\n)*$/, '')
  return trimmedStr + newlineChar
}
