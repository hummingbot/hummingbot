'use strict'

var convert = require('unist-util-is/convert')

module.exports = remove

function remove(ast, opts, test) {
  var is
  var cascade

  if (!test) {
    test = opts
    opts = {}
  }

  cascade = opts.cascade
  cascade = cascade === null || cascade === undefined ? true : cascade
  is = convert(test)

  return preorder(ast, null, null)

  // Check and remove nodes recursively in preorder.
  // For each composite node, modify its children array in-place.
  function preorder(node, nodeIndex, parent) {
    var children
    var length
    var index
    var position
    var child

    if (is(node, nodeIndex, parent)) {
      return null
    }

    children = node.children

    if (!children || children.length === 0) {
      return node
    }

    // Move all living children to the beginning of the children array.
    position = 0
    length = children.length
    index = -1

    while (++index < length) {
      child = preorder(children[index], index, node)

      if (child) {
        children[position++] = child
      }
    }

    // Cascade delete.
    if (cascade && position === 0) {
      return null
    }

    // Drop other nodes.
    children.length = position

    return node
  }
}
