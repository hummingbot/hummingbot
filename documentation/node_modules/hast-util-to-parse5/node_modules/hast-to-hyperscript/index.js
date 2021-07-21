'use strict'

var html = require('property-information/html')
var svg = require('property-information/svg')
var find = require('property-information/find')
var hastToReact = require('property-information/hast-to-react.json')
var spaces = require('space-separated-tokens')
var commas = require('comma-separated-tokens')
var style = require('style-to-object')
var ns = require('web-namespaces')
var convert = require('unist-util-is/convert')

var root = convert('root')
var element = convert('element')
var text = convert('text')

var dashes = /-([a-z])/g

module.exports = wrapper

function wrapper(h, node, options) {
  var settings = options || {}
  var prefix
  var r
  var v
  var vd

  if (typeof h !== 'function') {
    throw new Error('h is not a function')
  }

  if (typeof settings === 'string' || typeof settings === 'boolean') {
    prefix = settings
    settings = {}
  } else {
    prefix = settings.prefix
  }

  r = react(h)
  v = vue(h)
  vd = vdom(h)

  if (prefix === null || prefix === undefined) {
    prefix = r === true || v === true || vd === true ? 'h-' : false
  }

  if (root(node)) {
    if (node.children.length === 1 && element(node.children[0])) {
      node = node.children[0]
    } else {
      node = {
        type: 'element',
        tagName: 'div',
        properties: {},
        children: node.children
      }
    }
  } else if (!element(node)) {
    throw new Error(
      'Expected root or element, not `' + ((node && node.type) || node) + '`'
    )
  }

  return toH(h, node, {
    schema: settings.space === 'svg' ? svg : html,
    prefix: prefix,
    key: 0,
    react: r,
    vue: v,
    vdom: vd,
    hyperscript: hyperscript(h)
  })
}

// Transform a hast node through a hyperscript interface to *anything*!
function toH(h, node, ctx) {
  var parentSchema = ctx.schema
  var schema = parentSchema
  var name = node.tagName
  var properties
  var attributes
  var children
  var property
  var elements
  var length
  var index
  var value
  var result

  if (parentSchema.space === 'html' && name.toLowerCase() === 'svg') {
    schema = svg
    ctx.schema = schema
  }

  if (ctx.vdom === true && schema.space === 'html') {
    name = name.toUpperCase()
  }

  properties = node.properties
  attributes = {}

  for (property in properties) {
    addAttribute(attributes, property, properties[property], ctx)
  }

  if (
    typeof attributes.style === 'string' &&
    (ctx.vdom === true || ctx.vue === true || ctx.react === true)
  ) {
    // VDOM, Vue, and React accept `style` as object.
    attributes.style = parseStyle(attributes.style, name)
  }

  if (ctx.prefix) {
    ctx.key++
    attributes.key = ctx.prefix + ctx.key
  }

  if (ctx.vdom && schema.space !== 'html') {
    attributes.namespace = ns[schema.space]
  }

  elements = []
  children = node.children
  length = children ? children.length : 0
  index = -1

  while (++index < length) {
    value = children[index]

    if (element(value)) {
      elements.push(toH(h, value, ctx))
    } else if (text(value)) {
      elements.push(value.value)
    }
  }

  // Ensure no React warnings are triggered for void elements having children
  // passed in.
  result =
    elements.length === 0
      ? h.call(node, name, attributes)
      : h.call(node, name, attributes, elements)

  // Restore parent schema.
  ctx.schema = parentSchema

  return result
}

function addAttribute(props, prop, value, ctx) {
  var hyperlike = ctx.hyperscript || ctx.vdom || ctx.vue
  var schema = ctx.schema
  var info = find(schema, prop)
  var subprop

  // Ignore nullish and `NaN` values.
  // Ignore `false` and falsey known booleans for hyperlike DSLs.
  if (
    value === null ||
    value === undefined ||
    value !== value ||
    (hyperlike && value === false) ||
    (hyperlike && info.boolean && !value)
  ) {
    return
  }

  if (value !== null && typeof value === 'object' && 'length' in value) {
    // Accept `array`.
    // Most props are space-separated.
    value = (info.commaSeparated ? commas : spaces).stringify(value)
  }

  // Treat `true` and truthy known booleans.
  if (info.boolean && ctx.hyperscript === true) {
    value = ''
  }

  if (ctx.vue) {
    if (prop !== 'style') {
      subprop = 'attrs'
    }
  } else if (!info.mustUseProperty) {
    if (ctx.vdom === true) {
      subprop = 'attributes'
    } else if (ctx.hyperscript === true) {
      subprop = 'attrs'
    }
  }

  if (subprop) {
    if (props[subprop] === undefined) {
      props[subprop] = {}
    }

    props[subprop][info.attribute] = value
  } else if (ctx.react && info.space) {
    props[hastToReact[info.property] || info.property] = value
  } else {
    props[info.attribute] = value
  }
}

// Check if `h` is `react.createElement`.
function react(h) {
  var node = h && h('div')
  return Boolean(
    node && ('_owner' in node || '_store' in node) && node.key === null
  )
}

// Check if `h` is `hyperscript`.
function hyperscript(h) {
  return Boolean(h && h.context && h.cleanup)
}

// Check if `h` is `virtual-dom/h`.
function vdom(h) {
  return h && h('div').type === 'VirtualNode'
}

function vue(h) {
  var node = h && h('div')
  return Boolean(node && node.context && node.context._isVue)
}

function parseStyle(value, tagName) {
  var result = {}

  try {
    style(value, iterator)
  } catch (error) {
    error.message =
      tagName + '[style]' + error.message.slice('undefined'.length)
    throw error
  }

  return result

  function iterator(name, value) {
    result[styleCase(name)] = value
  }
}

function styleCase(value) {
  if (value.slice(0, 4) === '-ms-') {
    value = 'ms-' + value.slice(4)
  }

  return value.replace(dashes, styleReplacer)
}

function styleReplacer($0, $1) {
  return $1.toUpperCase()
}
