"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.duplicateOperationTypeMessage = duplicateOperationTypeMessage;
exports.existedOperationTypeMessage = existedOperationTypeMessage;
exports.UniqueOperationTypes = UniqueOperationTypes;

var _GraphQLError = require("../../error/GraphQLError");

function duplicateOperationTypeMessage(operation) {
  return "There can be only one ".concat(operation, " type in schema.");
}

function existedOperationTypeMessage(operation) {
  return "Type for ".concat(operation, " already defined in the schema. It cannot be redefined.");
}
/**
 * Unique operation types
 *
 * A GraphQL document is only valid if it has only one type per operation.
 */


function UniqueOperationTypes(context) {
  var schema = context.getSchema();
  var definedOperationTypes = Object.create(null);
  var existingOperationTypes = schema ? {
    query: schema.getQueryType(),
    mutation: schema.getMutationType(),
    subscription: schema.getSubscriptionType()
  } : {};
  return {
    SchemaDefinition: checkOperationTypes,
    SchemaExtension: checkOperationTypes
  };

  function checkOperationTypes(node) {
    if (node.operationTypes) {
      for (var _i2 = 0, _ref2 = node.operationTypes || []; _i2 < _ref2.length; _i2++) {
        var operationType = _ref2[_i2];
        var operation = operationType.operation;
        var alreadyDefinedOperationType = definedOperationTypes[operation];

        if (existingOperationTypes[operation]) {
          context.reportError(new _GraphQLError.GraphQLError(existedOperationTypeMessage(operation), operationType));
        } else if (alreadyDefinedOperationType) {
          context.reportError(new _GraphQLError.GraphQLError(duplicateOperationTypeMessage(operation), [alreadyDefinedOperationType, operationType]));
        } else {
          definedOperationTypes[operation] = operationType;
        }
      }
    }

    return false;
  }
}
