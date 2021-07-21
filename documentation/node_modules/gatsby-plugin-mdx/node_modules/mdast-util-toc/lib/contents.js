'use strict'

module.exports = contents

var LIST = 'list'
var LIST_ITEM = 'listItem'
var PARAGRAPH = 'paragraph'
var LINK = 'link'
var TEXT = 'text'

// Transform a list of heading objects to a markdown list.
function contents(map, tight) {
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
    insert(map[index], table, tight)
  }

  return table
}

// Insert a `node` into a `parent`.
function insert(node, parent, tight) {
  var children = parent.children
  var length = children.length
  var last = children[length - 1]
  var isLoose = false
  var index
  var item

  if (node.depth === 1) {
    item = listItem()

    item.children.push({
      type: PARAGRAPH,
      children: [
        {
          type: LINK,
          title: null,
          url: '#' + node.id,
          children: [{type: TEXT, value: node.value}]
        }
      ]
    })

    children.push(item)
  } else if (last && last.type === LIST_ITEM) {
    insert(node, last, tight)
  } else if (last && last.type === LIST) {
    node.depth--

    insert(node, last, tight)
  } else if (parent.type === LIST) {
    item = listItem()

    insert(node, item, tight)

    children.push(item)
  } else {
    item = list()
    node.depth--

    insert(node, item, tight)

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

  // To do: remove `loose` in next major release.
  if (parent.type === LIST_ITEM) {
    parent.loose = tight ? false : children.length > 1
  } else {
    if (tight) {
      isLoose = false
    } else {
      index = -1

      while (++index < length) {
        if (children[index].loose) {
          isLoose = true

          break
        }
      }
    }

    index = -1

    while (++index < length) {
      children[index].loose = isLoose
    }
  }
}

// Create a list.
function list() {
  return {type: LIST, ordered: false, spread: false, children: []}
}

// Create a list item.
function listItem() {
  // To do: remove `loose` in next major.
  return {type: LIST_ITEM, loose: false, spread: false, children: []}
}
