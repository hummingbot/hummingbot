module.exports = markdownLineEnding

var codes = require('./codes')

function markdownLineEnding(code) {
  return code < codes.horizontalTab
}
