'use strict'

var extend = require('extend')

module.exports = contents

var LIST = 'list'
var LIST_ITEM = 'listItem'
var PARAGRAPH = 'paragraph'
var LINK = 'link'
var LINK_REFERENCE = 'linkReference'
var FOOTNOTE = 'footnote'
var FOOTNOTE_REFERENCE = 'footnoteReference'

// Transform a list of heading objects to a markdown list.
function contents(map, tight, prefix) {
  var minDepth = Infinity
  var index = -1
  var length = map.length
  var table

  // Find minimum depth.
  while (++index < length) {
    if (map[index].depth < minDepth) {
      minDepth = map[index].depth
    }
  }

  // Normalize depth.
  index = -1

  while (++index < length) {
    map[index].depth -= minDepth - 1
  }

  // Construct the main list.
  table = list()

  // Add TOC to list.
  index = -1

  while (++index < length) {
    insert(map[index], table, tight, prefix)
  }

  return table
}

// Insert an entry into `parent`.
function insert(entry, parent, tight, prefix) {
  var children = parent.children
  var length = children.length
  var last = children[length - 1]
  var index
  var item

  if (entry.depth === 1) {
    item = listItem()

    item.children.push({
      type: PARAGRAPH,
      children: [
        {
          type: LINK,
          title: null,
          url: '#' + (prefix || '') + entry.id,
          children: all(entry.children)
        }
      ]
    })

    children.push(item)
  } else if (last && last.type === LIST_ITEM) {
    insert(entry, last, tight, prefix)
  } else if (last && last.type === LIST) {
    entry.depth--

    insert(entry, last, tight, prefix)
  } else if (parent.type === LIST) {
    item = listItem()

    insert(entry, item, tight, prefix)

    children.push(item)
  } else {
    item = list()
    entry.depth--

    insert(entry, item, tight, prefix)

    children.push(item)
  }

  // Properly style list-items with new lines.
  parent.spread = !tight

  if (parent.type === LIST && parent.spread) {
    parent.spread = false
    index = -1

    while (++index < length) {
      if (children[index].children.length > 1) {
        parent.spread = true
        break
      }
    }
  }
}

function all(children) {
  var result = []
  var length = children ? children.length : 0
  var index = -1

  while (++index < length) {
    result = result.concat(one(children[index]))
  }

  return result
}

function one(node) {
  var copy

  if (
    node.type === LINK ||
    node.type === LINK_REFERENCE ||
    node.type === FOOTNOTE ||
    node.type === FOOTNOTE_REFERENCE
  ) {
    return all(node.children)
  }

  copy = extend({}, node)

  delete copy.children
  delete copy.position

  copy = extend(true, {}, copy)

  if (node.children) {
    copy.children = all(node.children)
  }

  return copy
}

// Create a list.
function list() {
  return {type: LIST, ordered: false, spread: false, children: []}
}

// Create a list item.
function listItem() {
  return {type: LIST_ITEM, spread: false, children: []}
}
