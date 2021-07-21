'use strict'

module.exports = generateFootnotes

var thematicBreak = require('./handlers/thematic-break')
var list = require('./handlers/list')
var wrap = require('./wrap')

function generateFootnotes(h) {
  var footnotes = h.footnotes
  var length = footnotes.length
  var index = -1
  var listItems = []
  var def
  var backReference
  var content
  var tail

  if (!length) {
    return null
  }

  while (++index < length) {
    def = footnotes[index]
    content = def.children.concat()
    tail = content[content.length - 1]
    backReference = {
      type: 'link',
      url: '#fnref-' + def.identifier,
      data: {hProperties: {className: ['footnote-backref']}},
      children: [{type: 'text', value: '↩'}]
    }

    if (!tail || tail.type !== 'paragraph') {
      tail = {type: 'paragraph', children: []}
      content.push(tail)
    }

    tail.children.push(backReference)

    listItems[index] = {
      type: 'listItem',
      data: {hProperties: {id: 'fn-' + def.identifier}},
      children: content,
      position: def.position
    }
  }

  return h(
    null,
    'div',
    {className: ['footnotes']},
    wrap(
      [
        thematicBreak(h),
        list(h, {type: 'list', ordered: true, children: listItems})
      ],
      true
    )
  )
}
