'use strict'

module.exports = search

var toString = require('mdast-util-to-string')
var visit = require('unist-util-visit')
var is = require('unist-util-is')
var slugs = require('github-slugger')()

var HEADING = 'heading'

// Search a node for a location.
function search(root, expression, settings) {
  var length = root.children.length
  var depth = null
  var lookingForToc = expression !== null
  var maxDepth = settings.maxDepth || 6
  var parents = settings.parents || root
  var map = []
  var headingIndex
  var closingIndex

  if (!lookingForToc) {
    headingIndex = -1
  }

  slugs.reset()

  // Visit all headings in `root`.  We `slug` all headings (to account for
  // duplicates), but only create a TOC from top-level headings.
  visit(root, HEADING, onheading)

  if (headingIndex && !closingIndex) {
    closingIndex = length + 1
  }

  if (headingIndex === undefined) {
    headingIndex = -1
    closingIndex = -1
    map = []
  }

  return {index: headingIndex, endIndex: closingIndex, map: map}

  function onheading(child, index, parent) {
    var value = toString(child)
    var id = child.data && child.data.hProperties && child.data.hProperties.id

    if (!is(parents, parent)) {
      return
    }

    if (lookingForToc) {
      if (isClosingHeading(child, depth)) {
        closingIndex = index
        lookingForToc = false
      }

      if (isOpeningHeading(child, depth, expression)) {
        headingIndex = index + 1
        depth = child.depth
      }
    }

    if (!lookingForToc && value && child.depth <= maxDepth) {
      map.push({depth: child.depth, value: value, id: slugs.slug(id || value)})
    }
  }
}

// Check if `node` is the main heading.
function isOpeningHeading(node, depth, expression) {
  return (
    depth === null &&
    node &&
    node.type === HEADING &&
    expression.test(toString(node))
  )
}

// Check if `node` is the next heading.
function isClosingHeading(node, depth) {
  return depth && node && node.type === HEADING && node.depth <= depth
}
