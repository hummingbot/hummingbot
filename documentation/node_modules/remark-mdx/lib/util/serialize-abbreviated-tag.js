'use strict'

module.exports = serializeAbbreviatedTag

// Serialize a tag, excluding attributes.
function serializeAbbreviatedTag(node) {
  return (
    '<' +
    (node.close ? '/' : '') +
    (node.name || '') +
    /* istanbul ignore next - currently not used on self-closing tags */
    (node.selfClosing ? '/' : '') +
    '>'
  )
}
