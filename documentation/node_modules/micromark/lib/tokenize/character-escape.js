exports.tokenize = tokenizeCharacterEscape

var assert = require('assert')
var codes = require('../character/codes')
var asciiPunctuation = require('../character/ascii-punctuation')
var types = require('../constant/types')

function tokenizeCharacterEscape(effects, ok, nok) {
  return start

  function start(code) {
    assert(code === codes.backslash, 'expected `\\`')
    effects.enter(types.characterEscape)
    effects.enter(types.escapeMarker)
    effects.consume(code)
    effects.exit(types.escapeMarker)
    return open
  }

  function open(code) {
    if (asciiPunctuation(code)) {
      effects.enter(types.characterEscapeValue)
      effects.consume(code)
      effects.exit(types.characterEscapeValue)
      effects.exit(types.characterEscape)
      return ok
    }

    return nok(code)
  }
}
