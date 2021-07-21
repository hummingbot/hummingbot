'use strict'

var stringifyEntities = require('stringify-entities')
var mdxExpression = require('./mdx-expression')
var indent = require('../util/indent')

module.exports = mdxElement

// Expose helper to create tags.
mdxElement.serializeTags = serializeTags

var lineFeed = '\n'
var space = ' '
var slash = '/'
var quotationMark = '"'
var lessThan = '<'
var equalsTo = '='
var greaterThan = '>'

var valueCharacterReferenceOptions = {
  useNamedReferences: true,
  subset: [quotationMark]
}

function mdxElement(node) {
  var tags = serializeTags(node)
  var block = node.type === 'mdxBlockElement'
  var content = this.all(node).join(block ? lineFeed + lineFeed : '')

  if (block && content) {
    content = lineFeed + indent(content) + lineFeed
  }

  return tags.open + content + (tags.close || '')
}

function serializeTags(node) {
  var block = node.type === 'mdxBlockElement'
  var name = String(node.name || '')
  var attributes = serializeAttributes(node.attributes || [], block)
  var selfClosing = name && node.children.length === 0

  if (name === '' && attributes !== '') {
    throw new Error('Cannot serialize fragment with attributes')
  }

  return {
    open: lessThan +
      name +
      attributes +
      (selfClosing ? slash : '') +
      greaterThan,
    close: selfClosing ? null : lessThan + slash + name + greaterThan
  }
}

function serializeAttributes(nodes, block) {
  var length = nodes.length
  var index = -1
  var result = []

  while (++index < length) {
    result.push(serializeAttribute(nodes[index]))
  }

  // None.
  if (result.length === 0) {
    return ''
  }

  // A block with multiple attributes
  if (block && result.length !== 1) {
    return lineFeed + indent(result.join(lineFeed)) + lineFeed
  }

  // A span, or a block with a single attribute.
  return space + dedentStart(indent(result.join(space)))
}

function serializeAttribute(node) {
  var fn = node.type === 'mdxAttributeExpression' ? mdxExpression : mdxAttribute
  return fn(node)
}

function serializeValue(value) {
  if (typeof value === 'object') {
    return mdxExpression(value)
  }

  return (
    quotationMark +
    stringifyEntities(value, valueCharacterReferenceOptions) +
    quotationMark
  )
}

function mdxAttribute(node) {
  var name = String(node.name || '')
  var value = node.value

  if (name === '') {
    throw new Error('Cannot serialize attribute without name')
  }

  if (value === null || value === undefined) {
    return name
  }

  return name + equalsTo + serializeValue(value)
}

function dedentStart(value) {
  return value.replace(/ +/, '')
}
