module.exports = createTitle

var assert = require('assert')
var markdownLineEnding = require('../character/markdown-line-ending')
var codes = require('../character/codes')
var constants = require('../constant/constants')
var types = require('../constant/types')
var createSpace = require('./factory-space')

// eslint-disable-next-line max-params
function createTitle(effects, ok, nok, type, markerType, stringType) {
  var marker

  return start

  function start(code) {
    assert(
      code === codes.quotationMark ||
        code === codes.apostrophe ||
        code === codes.leftParenthesis,
      'expected `"`, `\'`, or `(`'
    )
    effects.enter(type)
    effects.enter(markerType)
    effects.consume(code)
    effects.exit(markerType)
    marker = code === codes.leftParenthesis ? codes.rightParenthesis : code
    return atFirstTitleBreak
  }

  function atFirstTitleBreak(code) {
    if (code === marker) {
      effects.enter(markerType)
      effects.consume(code)
      effects.exit(markerType)
      effects.exit(type)
      return ok
    }

    effects.enter(stringType)
    return atTitleBreak(code)
  }

  function atTitleBreak(code) {
    if (code === marker) {
      effects.exit(stringType)
      return atFirstTitleBreak(marker)
    }

    if (code === codes.eof) {
      return nok(code)
    }

    // Note: blank lines can’t exist in content.
    if (markdownLineEnding(code)) {
      effects.enter(types.lineEnding)
      effects.consume(code)
      effects.exit(types.lineEnding)
      return createSpace(effects, atTitleBreak, types.linePrefix)
    }

    effects.enter(types.chunkString, {contentType: constants.contentTypeString})
    return title(code)
  }

  function title(code) {
    if (code === marker || code === codes.eof || markdownLineEnding(code)) {
      effects.exit(types.chunkString)
      return atTitleBreak(code)
    }

    effects.consume(code)
    return code === codes.backslash ? titleEscape : title
  }

  function titleEscape(code) {
    if (code === marker || code === codes.backslash) {
      effects.consume(code)
      return title
    }

    return title(code)
  }
}
