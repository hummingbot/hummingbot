'use strict'

var stripIndent = require('strip-indent')

module.exports = dedentExpression

var lineFeed = '\n'

function dedentExpression(value) {
  var lines = value.trim().split(lineFeed)
  var head = lines.shift()
  var rest = stripIndent(lines.join(lineFeed))
  return head + (rest ? lineFeed + rest : '')
}
