'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var schema = [{
  enum: ['always', 'never'],
  type: 'string'
}];

var create = function create(context) {
  return {
    ObjectTypeAnnotation(node) {
      var properties = node.properties;


      properties.forEach(function (property) {
        var type = property.type;

        if (type === 'ObjectTypeSpreadProperty') {
          var _property$argument = property.argument,
              argumentType = _property$argument.type,
              argumentId = _property$argument.id;

          if (argumentType !== 'GenericTypeAnnotation' || argumentId.name !== '$Exact') {
            context.report({
              message: 'Use $Exact to make type spreading safe.',
              node
            });
          }
        }
      });
    }
  };
};

exports.default = {
  create,
  schema
};
module.exports = exports.default;