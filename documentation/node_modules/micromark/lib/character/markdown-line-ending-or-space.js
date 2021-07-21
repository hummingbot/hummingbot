module.exports = markdownLineEndingOrSpace

var codes = require('./codes')

function markdownLineEndingOrSpace(code) {
  return code < codes.nul || code === codes.space
}
