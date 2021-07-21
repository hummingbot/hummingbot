exports.tokenize = tokenizeCharacterReference

var assert = require('assert')
var decode = require('parse-entities/decode-entity')
var asciiAlphanumeric = require('../character/ascii-alphanumeric')
var asciiDigit = require('../character/ascii-digit')
var asciiHexDigit = require('../character/ascii-hex-digit')
var codes = require('../character/codes')
var constants = require('../constant/constants')
var types = require('../constant/types')

function tokenizeCharacterReference(effects, ok, nok) {
  var self = this
  var size = 0
  var max
  var test

  return start

  function start(code) {
    assert(code === codes.ampersand, 'expected `&`')
    effects.enter(types.characterReference)
    effects.enter(types.characterReferenceMarker)
    effects.consume(code)
    effects.exit(types.characterReferenceMarker)
    return open
  }

  function open(code) {
    if (code === codes.numberSign) {
      effects.enter(types.characterReferenceMarkerNumeric)
      effects.consume(code)
      effects.exit(types.characterReferenceMarkerNumeric)
      return numeric
    }

    effects.enter(types.characterReferenceValue)
    max = constants.characterReferenceNamedSizeMax
    test = asciiAlphanumeric
    return value(code)
  }

  function numeric(code) {
    if (code === codes.uppercaseX || code === codes.lowercaseX) {
      effects.enter(types.characterReferenceMarkerHexadecimal)
      effects.consume(code)
      effects.exit(types.characterReferenceMarkerHexadecimal)
      effects.enter(types.characterReferenceValue)
      max = constants.characterReferenceHexadecimalSizeMax
      test = asciiHexDigit
      return value
    }

    effects.enter(types.characterReferenceValue)
    max = constants.characterReferenceDecimalSizeMax
    test = asciiDigit
    return value(code)
  }

  function value(code) {
    var token

    if (code === codes.semicolon && size) {
      token = effects.exit(types.characterReferenceValue)

      if (test === asciiAlphanumeric && !decode(self.sliceSerialize(token))) {
        return nok(code)
      }

      effects.enter(types.characterReferenceMarker)
      effects.consume(code)
      effects.exit(types.characterReferenceMarker)
      effects.exit(types.characterReference)
      return ok
    }

    if (test(code) && size++ < max) {
      effects.consume(code)
      return value
    }

    return nok(code)
  }
}
