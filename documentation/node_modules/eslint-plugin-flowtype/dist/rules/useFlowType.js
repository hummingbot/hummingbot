'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var schema = [];

var create = function create(context) {
  var markTypeAsUsed = function markTypeAsUsed(node) {
    context.markVariableAsUsed(node.id.name);
  };
  var markTypeAsUsedWithGenericType = function markTypeAsUsedWithGenericType(node) {
    var typeId = void 0;
    var scope = void 0;
    var variable = void 0;

    if (node.id.type === 'Identifier') {
      typeId = node.id;
    } else if (node.id.type === 'QualifiedTypeIdentifier') {
      typeId = node.id;
      do {
        typeId = typeId.qualification;
      } while (typeId.qualification);
    }

    for (scope = context.getScope(); scope; scope = scope.upper) {
      variable = scope.set.get(typeId.name);
      if (variable && variable.defs.length) {
        context.markVariableAsUsed(typeId.name);
        break;
      }
    }
  };

  return {
    DeclareClass: markTypeAsUsed,
    DeclareFunction: markTypeAsUsed,
    DeclareModule: markTypeAsUsed,
    DeclareVariable: markTypeAsUsed,
    GenericTypeAnnotation: markTypeAsUsedWithGenericType,
    TypeParameterDeclaration(node) {
      node.params.forEach(function (param) {
        if (param.default && param.default.typeParameters) {
          if (param.default.type === 'GenericTypeAnnotation') {
            markTypeAsUsedWithGenericType(param.default);
          }

          param.default.typeParameters.params.forEach(function (typeParameterNode) {
            if (typeParameterNode.type === 'GenericTypeAnnotation') {
              markTypeAsUsedWithGenericType(typeParameterNode);
            }
          });
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