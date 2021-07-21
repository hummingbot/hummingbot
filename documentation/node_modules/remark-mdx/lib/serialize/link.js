'use strict'

// Copied and modified from remark-stringify
// Original source: https://github.com/remarkjs/remark/blob/19a27c30b13baa3a9e864e528c6a0b901a5fc918/packages/remark-stringify/lib/visitors/link.js
// License (MIT): https://github.com/remarkjs/remark/blob/main/license

var uri = require('remark-stringify/lib/util/enclose-uri')
var title = require('remark-stringify/lib/util/enclose-title')

module.exports = link

var space = ' '
var leftSquareBracket = '['
var rightSquareBracket = ']'
var leftParenthesis = '('
var rightParenthesis = ')'

// Expression for a protocol:
// See <https://en.wikipedia.org/wiki/Uniform_Resource_Identifier#Generic_syntax>.
var protocol = /^[a-z][a-z+.-]+:\/?/i

// Stringify a link.
//
// With MDX we don't support <https://mdxjs.com> style links, which is the default
// for remark-stringify (understandably). So, we check for the case where the url
// and its text are equal. If it is, we serialize/stringify link syntax with the
// url as the title rather than wrapping it in angle brackets (<>).
//
// ```markdown
// [http://example.com](http://example.com)
// ```
//
// Otherwise, is smart about enclosing `url` (see `encloseURI()`) and `title`
// (see `encloseTitle()`).
// ```
//
// ```markdown
// [foo](<foo at bar dot com> 'An "example" e-mail')
// ```
//
// Supports named entities in the `url` and `title` when in `settings.encode`
// mode.
function link(node) {
  var self = this
  var content = self.encode(node.url || '', node)
  var exit = self.enterLink()
  var value = self.all(node).join('')

  exit()

  content = uri(content)

  if (node.title) {
    content += space + title(self.encode(self.escape(node.title, node), node))
  }

  return (
    leftSquareBracket +
    value +
    rightSquareBracket +
    leftParenthesis +
    content +
    rightParenthesis
  )
}
