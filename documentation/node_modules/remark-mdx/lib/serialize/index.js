'use strict'

var mdxExpression = require('./mdx-expression')
var mdxElement = require('./mdx-element')
var link = require('./link')
var text = require('./text')

module.exports = serialize

function serialize(compiler) {
  var proto = compiler.prototype
  var visitors = proto.visitors

  // Serialize code blocks with fences.
  proto.options.fences = true

  // Add serializers.
  visitors.mdxSpanExpression = mdxExpression
  visitors.mdxBlockExpression = mdxExpression
  visitors.mdxSpanElement = mdxElement
  visitors.mdxBlockElement = mdxElement
  visitors.link = link
  visitors.text = text
}
