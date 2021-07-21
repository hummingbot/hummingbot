exports.tokenize = tokenizeWhitespace

var markdownLineEnding = require('../character/markdown-line-ending')

var createSpace = require('./factory-space')

function tokenizeWhitespace(effects, ok) {
  return start

  function start(code) {
    effects.enter('lineEnding')
    effects.consume(code)
    effects.exit('lineEnding')
    return createSpace(effects, ok, 'linePrefix')
  }
}
