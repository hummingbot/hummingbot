'use strict'

module.exports = react

var toHAST = require('mdast-util-to-hast')
var sanitize = require('hast-util-sanitize')
var toH = require('hast-to-hyperscript')
var tableCellStyle = require('@mapbox/hast-util-table-cell-style')

var globalReact
var globalCreateElement
var globalFragment

/* istanbul ignore next - Hard to test */
try {
  globalReact = require('react')
  globalCreateElement = globalReact.createElement
  globalFragment = globalReact.Fragment
} catch (error) {}

var own = {}.hasOwnProperty

function react(options) {
  var settings = options || {}
  var createElement = settings.createElement || globalCreateElement
  var Fragment = settings.fragment || globalFragment
  var clean = settings.sanitize !== false
  var scheme =
    clean && typeof settings.sanitize !== 'boolean' ? settings.sanitize : null
  var toHastOptions = settings.toHast || {}
  var components = settings.remarkReactComponents || {}

  this.Compiler = compile

  // Wrapper around `createElement` to pass components in.
  function h(name, props, children) {
    return createElement(
      own.call(components, name) ? components[name] : name,
      props,
      children
    )
  }

  // Compile mdast to React.
  function compile(node) {
    var tree = toHAST(node, toHastOptions)
    var root

    if (clean) {
      tree = sanitize(tree, scheme)
    }

    root = toH(h, tableCellStyle(tree), settings.prefix)

    // If this compiled to a `<div>`, but fragment are possible, use those.
    if (root.type === 'div' && Fragment) {
      root = createElement(Fragment, {}, root.props.children)
    }

    return root
  }
}
