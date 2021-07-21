'use strict'

var stringifyEntities = require('stringify-entities')

module.exports = text

var expressionCharacterReferenceOptions = {
  useNamedReferences: true,
  // Note: we don’t encode `>` or `}`, as we don’t crash on parsing them
  // either.
  subset: ['<', '{']
}

function text(node, parent) {
  return stringifyEntities(
    this.escape(node.value, node, parent),
    expressionCharacterReferenceOptions
  )
}
