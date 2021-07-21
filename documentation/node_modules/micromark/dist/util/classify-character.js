module.exports = classifyCharacter

var markdownLineEndingOrSpace = require('../character/markdown-line-ending-or-space')
var unicodePunctuation = require('../character/unicode-punctuation')
var unicodeWhitespace = require('../character/unicode-whitespace')

// Classify whether a character is unicode whitespace, unicode punctuation, or
// anything else.
// Used for attention (emphasis, strong), whose sequences can open or close
// based on the class of surrounding characters.
function classifyCharacter(code) {
  if (
    code === null ||
    markdownLineEndingOrSpace(code) ||
    unicodeWhitespace(code)
  ) {
    return 1
  }

  if (unicodePunctuation(code)) {
    return 2
  }
}
