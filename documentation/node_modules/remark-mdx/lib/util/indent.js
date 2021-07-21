'use strict'

module.exports = indent

var lineFeed = '\n'
var before = '  '
var content = /\S/

function indent(value) {
  var lines = value.split(lineFeed)
  var length = lines.length
  var index = -1
  var line

  while (++index < length) {
    line = lines[index]
    lines[index] = content.test(line) ? before + line : line
  }

  return lines.join(lineFeed)
}
