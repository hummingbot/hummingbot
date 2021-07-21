module.exports = markdownLineEndingOrSpace

function markdownLineEndingOrSpace(code) {
  return code < 0 || code === 32
}
