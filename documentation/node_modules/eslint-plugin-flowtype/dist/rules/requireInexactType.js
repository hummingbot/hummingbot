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

  return {
    ObjectTypeAnnotation(node) {
      var inexact = node.inexact,
          exact = node.exact;


      if (!node.hasOwnProperty('inexact')) {
        return;
      }

      if (always && !inexact && !exact) {
        context.report({
          message: 'Type must be explicit inexact.',
          node
        });
      }

      if (!always && inexact) {
        context.report({
          message: 'Type must not be explicit inexact.',
          node
        });
      }
    }
  };
};

exports.default = {
  create,
  schema
};
module.exports = exports.default;