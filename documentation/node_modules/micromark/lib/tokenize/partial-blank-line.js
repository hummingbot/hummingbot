exports.tokenize = tokenizeBlankLine
exports.partial = true

var markdownLineEnding = require('../character/markdown-line-ending')
var codes = require('../character/codes')
var types = require('../constant/types')
var createSpace = require('./factory-space')

function tokenizeBlankLine(effects, ok, nok) {
  return createSpace(effects, afterWhitespace, types.linePrefix)

  function afterWhitespace(code) {
    return code === codes.eof || markdownLineEnding(code) ? ok(code) : nok(code)
  }
}
