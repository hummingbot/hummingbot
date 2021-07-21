exports.tokenize = tokenizelabelLink
exports.resolveAll = require('./label-end').resolveAll

var assert = require('assert')
var codes = require('../character/codes')
var types = require('../constant/types')

function tokenizelabelLink(effects, ok, nok) {
  var self = this

  return start

  function start(code) {
    assert(code === codes.leftSquareBracket, 'expected `[`')
    effects.enter(types.labelLink)
    effects.enter(types.labelMarker)
    effects.consume(code)
    effects.exit(types.labelMarker)
    effects.exit(types.labelLink)
    return after
  }

  function after(code) {
    /* istanbul ignore next - footnotes. */
    return code === codes.caret &&
      '_hiddenFootnoteSupport' in self.parser.constructs
      ? nok(code)
      : ok(code)
  }
}
