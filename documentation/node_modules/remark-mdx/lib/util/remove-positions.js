'use strict'

module.exports = remove

function remove(node) {
  if ('length' in node) {
    node.forEach(remove)
  } else {
    delete node.position

    if (node.type === 'mdxTag') {
      remove(node.attributes)
    } else if (
      node.type === 'mdxAttribute' &&
      node.value &&
      typeof node.value === 'object'
    ) {
      remove(node.value)
    }
  }
}
