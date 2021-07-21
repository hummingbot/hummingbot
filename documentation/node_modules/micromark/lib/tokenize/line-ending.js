exports.tokenize = tokenizeWhitespace

var assert = require('assert')
var markdownLineEnding = require('../character/markdown-line-ending')
var types = require('../constant/types')
var createSpace = require('./factory-space')

function tokenizeWhitespace(effects, ok) {
  return start

  function start(code) {
    assert(markdownLineEnding(code), 'expected eol')
    effects.enter(types.lineEnding)
    effects.consume(code)
    effects.exit(types.lineEnding)
    return createSpace(effects, ok, types.linePrefix)
  }
}
