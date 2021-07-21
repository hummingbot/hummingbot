'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var schema = [];

var create = function create(context) {
  return {
    MixedTypeAnnotation(node) {
      context.report({
        message: 'Unexpected use of mixed type',
        node
      });
    }
  };
};

exports.default = {
  create,
  schema
};
module.exports = exports.default;