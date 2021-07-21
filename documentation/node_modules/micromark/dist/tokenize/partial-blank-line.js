exports.tokenize = tokenizeBlankLine
exports.partial = true

var markdownLineEnding = require('../character/markdown-line-ending')

var createSpace = require('./factory-space')

function tokenizeBlankLine(effects, ok, nok) {
  return createSpace(effects, afterWhitespace, 'linePrefix')

  function afterWhitespace(code) {
    return code === null || markdownLineEnding(code) ? ok(code) : nok(code)
  }
}
