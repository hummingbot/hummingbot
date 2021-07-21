'use strict'

var xtend = require('xtend')
var defaults = require('./github.json')

module.exports = wrapper

var own = {}.hasOwnProperty

var allData = 'data*'

var nodeSchema = {
  root: {children: all},
  doctype: handleDoctype,
  comment: handleComment,
  element: {
    tagName: handleTagName,
    properties: handleProperties,
    children: all
  },
  text: {value: handleValue},
  '*': {
    data: allow,
    position: allow
  }
}

// Sanitize `node`, according to `schema`.
function wrapper(node, schema) {
  var ctx = {type: 'root', children: []}
  var replace

  if (!node || typeof node !== 'object' || !node.type) {
    return ctx
  }

  replace = one(xtend(defaults, schema || {}), node, [])

  if (!replace) {
    return ctx
  }

  if ('length' in replace) {
    if (replace.length === 1) {
      return replace[0]
    }

    ctx.children = replace

    return ctx
  }

  return replace
}

// Sanitize `node`.
function one(schema, node, stack) {
  var type = node && node.type
  var replacement = {type: node.type}
  var replace = true
  var definition
  var allowed
  var result
  var key

  if (!own.call(nodeSchema, type)) {
    replace = false
  } else {
    definition = nodeSchema[type]

    if (typeof definition === 'function') {
      definition = definition(schema, node)
    }

    if (!definition) {
      replace = false
    } else {
      allowed = xtend(definition, nodeSchema['*'])

      for (key in allowed) {
        result = allowed[key](schema, node[key], node, stack)

        if (result === false) {
          replace = false

          // Set the non-safe value.
          replacement[key] = node[key]
        } else if (result !== null && result !== undefined) {
          replacement[key] = result
        }
      }
    }
  }

  if (!replace) {
    if (
      !replacement.children ||
      replacement.children.length === 0 ||
      schema.strip.indexOf(replacement.tagName) !== -1
    ) {
      return null
    }

    return replacement.children
  }

  return replacement
}

// Sanitize `children`.
function all(schema, children, node, stack) {
  var nodes = children || []
  var length = nodes.length || 0
  var results = []
  var index = -1
  var result

  stack = stack.concat(node.tagName)

  while (++index < length) {
    result = one(schema, nodes[index], stack)

    if (result) {
      if ('length' in result) {
        results = results.concat(result)
      } else {
        results.push(result)
      }
    }
  }

  return results
}

// Sanitize `properties`.
function handleProperties(schema, properties, node, stack) {
  var name = handleTagName(schema, node.tagName, node, stack)
  var attrs = schema.attributes
  var reqs = schema.required || /* istanbul ignore next */ {}
  var props = properties || {}
  var result = {}
  var allowed
  var required
  var definition
  var prop
  var value

  allowed = xtend(
    toPropertyValueMap(attrs['*']),
    toPropertyValueMap(own.call(attrs, name) ? attrs[name] : [])
  )

  for (prop in props) {
    value = props[prop]

    if (own.call(allowed, prop)) {
      definition = allowed[prop]
    } else if (data(prop) && own.call(allowed, allData)) {
      definition = allowed[allData]
    } else {
      continue
    }

    if (value && typeof value === 'object' && 'length' in value) {
      value = handlePropertyValues(schema, value, prop, definition)
    } else {
      value = handlePropertyValue(schema, value, prop, definition)
    }

    if (value !== null && value !== undefined) {
      result[prop] = value
    }
  }

  required = own.call(reqs, name) ? reqs[name] : {}

  for (prop in required) {
    if (!own.call(result, prop)) {
      result[prop] = required[prop]
    }
  }

  return result
}

// Sanitize a property value which is a list.
function handlePropertyValues(schema, values, prop, definition) {
  var length = values.length
  var result = []
  var index = -1
  var value

  while (++index < length) {
    value = handlePropertyValue(schema, values[index], prop, definition)

    if (value !== null && value !== undefined) {
      result.push(value)
    }
  }

  return result
}

// Sanitize a property value.
function handlePropertyValue(schema, value, prop, definition) {
  if (
    typeof value !== 'boolean' &&
    typeof value !== 'number' &&
    typeof value !== 'string'
  ) {
    return null
  }

  if (!handleProtocol(schema, value, prop)) {
    return null
  }

  if (definition.length !== 0 && definition.indexOf(value) === -1) {
    return null
  }

  if (schema.clobber.indexOf(prop) !== -1) {
    value = schema.clobberPrefix + value
  }

  return value
}

// Check whether `value` is a safe URL.
function handleProtocol(schema, value, prop) {
  var protocols = schema.protocols
  var protocol
  var first
  var colon
  var length
  var index

  protocols = own.call(protocols, prop) ? protocols[prop].concat() : []

  if (protocols.length === 0) {
    return true
  }

  value = String(value)
  first = value.charAt(0)

  if (first === '#' || first === '/') {
    return true
  }

  colon = value.indexOf(':')

  if (colon === -1) {
    return true
  }

  length = protocols.length
  index = -1

  while (++index < length) {
    protocol = protocols[index]

    if (
      colon === protocol.length &&
      value.slice(0, protocol.length) === protocol
    ) {
      return true
    }
  }

  index = value.indexOf('?')

  if (index !== -1 && colon > index) {
    return true
  }

  index = value.indexOf('#')

  if (index !== -1 && colon > index) {
    return true
  }

  return false
}

// Always return a valid HTML5 doctype.
function handleDoctypeName() {
  return 'html'
}

// Sanitize `tagName`.
function handleTagName(schema, tagName, node, stack) {
  var name = typeof tagName === 'string' ? tagName : null
  var ancestors = schema.ancestors
  var length
  var index

  if (!name || name === '*' || schema.tagNames.indexOf(name) === -1) {
    return false
  }

  ancestors = own.call(ancestors, name) ? ancestors[name] : []

  // Some nodes can break out of their context if they don’t have a certain
  // ancestor.
  if (ancestors.length !== 0) {
    length = ancestors.length + 1
    index = -1

    while (++index < length) {
      if (!ancestors[index]) {
        return false
      }

      if (stack.indexOf(ancestors[index]) !== -1) {
        break
      }
    }
  }

  return name
}

function handleDoctype(schema) {
  return schema.allowDoctypes ? {name: handleDoctypeName} : null
}

function handleComment(schema) {
  return schema.allowComments ? {value: handleValue} : null
}

// Sanitize `value`.
function handleValue(schema, value) {
  return typeof value === 'string' ? value : ''
}

// Create a map from a list of props or a list of properties and values.
function toPropertyValueMap(values) {
  var result = {}
  var length = values.length
  var index = -1
  var value

  while (++index < length) {
    value = values[index]

    if (value && typeof value === 'object' && 'length' in value) {
      result[value[0]] = value.slice(1)
    } else {
      result[value] = []
    }
  }

  return result
}

// Allow `value`.
function allow(schema, value) {
  return value
}

// Check if `prop` is a data property.
function data(prop) {
  return prop.length > 4 && prop.slice(0, 4).toLowerCase() === 'data'
}
