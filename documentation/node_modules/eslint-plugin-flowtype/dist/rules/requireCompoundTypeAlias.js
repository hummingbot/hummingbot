'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var schema = [{
  enum: ['always', 'never'],
  type: 'string'
}];

var create = function create(context) {
  var always = (context.options[0] || 'always') === 'always';

  if (always) {
    return {
      IntersectionTypeAnnotation(node) {
        if (node.parent.type !== 'TypeAlias') {
          context.report({
            message: 'All intersection types must be declared with named type alias.',
            node
          });
        }
      },
      UnionTypeAnnotation(node) {
        if (node.parent.type !== 'TypeAlias') {
          context.report({
            message: 'All union types must be declared with named type alias.',
            node
          });
        }
      }
    };
  } else {
    return {};
  }
};

exports.default = {
  create,
  schema
};
module.exports = exports.default;