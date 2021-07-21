module.exports = markdownSpace

function markdownSpace(code) {
  return code === -2 || code === -1 || code === 32
}
