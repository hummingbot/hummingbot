'use strict'

var indent = require('../util/indent')

module.exports = mdxExpression

var leftCurlyBrace = '{'
var rightCurlyBrace = '}'

function mdxExpression(node) {
  var value = node.value || ''
  var block = node.type === 'mdxBlockExpression'
  var around = block ? '\n' : ''
  var content = block ? indent(value) : value
  return leftCurlyBrace + around + content + around + rightCurlyBrace
}
