module.exports = createSpace

var markdownSpace = require('../character/markdown-space')

function createSpace(effects, ok, type, max) {
  var limit = max ? max - 1 : Infinity
  var size

  return start

  function start(code) {
    if (markdownSpace(code)) {
      effects.enter(type)
      size = 0
      return prefix(code)
    }

    return ok(code)
  }

  function prefix(code) {
    if (markdownSpace(code) && size++ < limit) {
      effects.consume(code)
      return prefix
    }

    effects.exit(type)
    return ok(code)
  }
}
