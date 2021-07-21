module.exports = toMarkdown

var zwitch = require('zwitch')
var defaultHandlers = require('./handle')
var defaultUnsafePatterns = require('./unsafe')
var defaultJoin = require('./join')

function toMarkdown(tree, options) {
  var settings = options || {}
  var extensions = configure(settings)
  var stack = []
  var handle = zwitch('type', {
    invalid: invalid,
    unknown: unknown,
    handlers: extensions.handlers
  })
  var context = {
    handle: handle,
    stack: stack,
    enter: enter,
    options: settings,
    unsafePatterns: extensions.unsafe,
    join: extensions.join
  }
  var result = handle(tree, null, context, {before: '\n', after: '\n'})

  if (
    result &&
    result.charCodeAt(result.length - 1) !== 10 &&
    result.charCodeAt(result.length - 1) !== 13
  ) {
    result += '\n'
  }

  return result

  function enter(name) {
    stack.push(name)
    return exit

    function exit() {
      stack.pop()
    }
  }
}

function invalid(value) {
  throw new Error('Cannot handle value `' + value + '`, expected node')
}

function unknown(node) {
  throw new Error('Cannot handle unknown node `' + node.type + '`')
}

function configure(settings) {
  var extensions = [
    {unsafe: settings.unsafe, handlers: settings.handlers, join: settings.join}
  ].concat(settings.extensions || [])
  var unsafe = defaultUnsafePatterns
  var join = defaultJoin
  var handlers = Object.assign({}, defaultHandlers)
  var index = -1

  if (settings.tightDefinitions) {
    join = [joinDefinition].concat(join)
  }

  while (++index < extensions.length) {
    unsafe = unsafe.concat(extensions[index].unsafe || [])
    join = join.concat(extensions[index].join || [])
    Object.assign(handlers, extensions[index].handlers || {})
  }

  return {unsafe: unsafe, join: join, handlers: handlers}
}

function joinDefinition(left, right) {
  // No blank line between adjacent definitions.
  if (left.type === 'definition' && left.type === right.type) {
    return 0
  }
}
