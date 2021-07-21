'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var schema = [{
  enum: ['declaration', 'identifier'],
  type: 'string'
}, {
  additionalProperties: false,
  properties: {
    ignoreTypeDefault: {
      type: 'boolean'
    }
  },
  type: 'object'
}];

var create = function create(context) {
  if (context.options[0] === 'declaration') {
    return {
      ImportDeclaration(node) {
        if (node.importKind !== 'type') {
          node.specifiers.forEach(function (specifier) {
            if (specifier.importKind === 'type') {
              context.report({
                message: 'Unexpected type import',
                node
              });
            }
          });
        }
      }
    };
  } else {
    // Default to 'identifier'
    var ignoreTypeDefault = context.options[1] && context.options[1].ignoreTypeDefault;
    var isInsideDeclareModule = false;

    return {
      DeclareModule() {
        isInsideDeclareModule = true;
      },
      'DeclareModule:exit'() {
        isInsideDeclareModule = false;
      },
      ImportDeclaration(node) {
        if (node.importKind !== 'type') {
          return;
        }

        // type specifiers are not allowed inside module declarations:
        // https://github.com/facebook/flow/issues/7609
        if (isInsideDeclareModule) {
          return;
        }

        if (ignoreTypeDefault && node.specifiers[0] && node.specifiers[0].type === 'ImportDefaultSpecifier') {
          return;
        }

        context.report({
          fix(fixer) {
            var imports = node.specifiers.map(function (specifier) {
              if (specifier.type === 'ImportDefaultSpecifier') {
                return 'type default as ' + specifier.local.name;
              } else if (specifier.imported.name === specifier.local.name) {
                return 'type ' + specifier.local.name;
              } else {
                return 'type ' + specifier.imported.name + ' as ' + specifier.local.name;
              }
            });
            var source = node.source.value;

            return fixer.replaceText(node, 'import {' + imports.join(', ') + '} from \'' + source + '\';');
          },
          message: 'Unexpected "import type"',
          node
        });
      }
    };
  }
};

exports.default = {
  create,
  schema
};
module.exports = exports.default;