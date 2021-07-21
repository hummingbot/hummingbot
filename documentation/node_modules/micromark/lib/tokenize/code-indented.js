exports.tokenize = tokenizeCodeIndented
exports.resolve = resolveCodeIndented

var assert = require('assert')
var codes = require('../character/codes')
var markdownLineEnding = require('../character/markdown-line-ending')
var constants = require('../constant/constants')
var types = require('../constant/types')
var chunkedSplice = require('../util/chunked-splice')
var prefixSize = require('../util/prefix-size')
var createSpace = require('./factory-space')

var continuedIndent = {tokenize: tokenizeContinuedIndent, partial: true}

function resolveCodeIndented(events, context) {
  var code = {
    type: types.codeIndented,
    start: events[0][1].start,
    end: events[events.length - 1][1].end
  }

  chunkedSplice(events, 0, 0, [['enter', code, context]])
  chunkedSplice(events, events.length, 0, [['exit', code, context]])

  return events
}

function tokenizeCodeIndented(effects, ok, nok) {
  var self = this

  return createSpace(
    effects,
    afterInitial,
    types.linePrefix,
    constants.tabSize + 1
  )

  function afterInitial(code) {
    // Flow checks blank lines first, so we don’t have EOL/EOF.
    assert(
      code !== codes.eof && !markdownLineEnding(code),
      'expected no eol or eof'
    )

    if (prefixSize(self.events, types.linePrefix) < constants.tabSize) {
      return nok(code)
    }

    effects.enter(types.codeFlowValue)
    return content(code)
  }

  function afterPrefix(code) {
    if (code === codes.eof) {
      return ok(code)
    }

    if (markdownLineEnding(code)) {
      return effects.attempt(continuedIndent, afterPrefix, ok)(code)
    }

    effects.enter(types.codeFlowValue)
    return content(code)
  }

  function content(code) {
    if (code === codes.eof || markdownLineEnding(code)) {
      effects.exit(types.codeFlowValue)
      return afterPrefix(code)
    }

    effects.consume(code)
    return content
  }
}

function tokenizeContinuedIndent(effects, ok, nok) {
  var self = this

  return createSpace(
    effects,
    afterPrefix,
    types.linePrefix,
    constants.tabSize + 1
  )

  function afterPrefix(code) {
    if (markdownLineEnding(code)) {
      effects.enter(types.lineEnding)
      effects.consume(code)
      effects.exit(types.lineEnding)

      return createSpace(
        effects,
        afterPrefix,
        types.linePrefix,
        constants.tabSize + 1
      )
    }

    return prefixSize(self.events, types.linePrefix) < constants.tabSize
      ? nok(code)
      : ok(code)
  }
}
