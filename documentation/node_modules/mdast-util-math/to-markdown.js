'use strict'

exports.unsafe = [
  {character: '\r', inConstruct: ['mathFlowMeta']},
  {character: '\r', inConstruct: ['mathFlowMeta']},
  {character: '$', inConstruct: ['mathFlowMeta', 'phrasing']},
  {atBreak: true, character: '$', after: '\\$'}
]

exports.handlers = {math: math, inlineMath: inlineMath}

inlineMath.peek = inlineMathPeek

var repeat = require('repeat-string')
var streak = require('longest-streak')
var safe = require('mdast-util-to-markdown/lib/util/safe')

function math(node, _, context) {
  var raw = node.value || ''
  var fence = repeat('$', Math.max(streak(raw, '$') + 1, 2))
  var exit = context.enter('mathFlow')
  var value = fence
  var subexit

  if (node.meta) {
    subexit = context.enter('mathFlowMeta')
    value += safe(context, node.meta, {before: '$', after: ' ', encode: ['$']})
    subexit()
  }

  value += '\n'

  if (raw) {
    value += raw + '\n'
  }

  value += fence
  exit()
  return value
}

function inlineMath(node) {
  var value = node.value || ''
  var size = 1
  var pad = ''
  var sequence

  // If there is a single dollar sign on its own in the math, use a fence of
  // two.
  // If there are two in a row, use one.
  while (
    new RegExp('(^|[^$])' + repeat('\\$', size) + '([^$]|$)').test(value)
  ) {
    size++
  }

  // If this is not just spaces or eols (tabs don’t count), and either the first
  // or last character are a space, eol, or dollar sign, then pad with spaces.
  if (
    /[^ \r\n]/.test(value) &&
    (/[ \r\n$]/.test(value.charAt(0)) ||
      /[ \r\n$]/.test(value.charAt(value.length - 1)))
  ) {
    pad = ' '
  }

  sequence = repeat('$', size)
  return sequence + pad + value + pad + sequence
}

function inlineMathPeek() {
  return '$'
}
