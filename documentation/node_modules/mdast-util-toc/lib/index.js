'use strict'

module.exports = toc

var search = require('./search')
var contents = require('./contents')
var toExpression = require('./to-expression')

// Get a TOC representation of `node`.
function toc(node, options) {
  var settings = options || {}
  var heading = settings.heading ? toExpression(settings.heading) : null
  var result = search(node, heading, settings)
  var map = result.map

  result.map =
    map.length === 0 ? null : contents(map, settings.tight, settings.prefix)

  // No given heading.
  if (!heading) {
    result.index = null
    result.endIndex = null
  }

  return result
}
