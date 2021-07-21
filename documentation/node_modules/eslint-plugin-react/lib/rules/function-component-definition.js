/**
 * @fileoverview Standardize the way function component get defined
 * @author Stefan Wullems
 */

'use strict';

const Components = require('../util/Components');
const docsUrl = require('../util/docsUrl');

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

function buildFunction(template, parts) {
  return Object.keys(parts)
    .reduce((acc, key) => acc.replace(`{${key}}`, parts[key] || ''), template);
}

const NAMED_FUNCTION_TEMPLATES = {
  'function-declaration': 'function {name}{typeParams}({params}){returnType} {body}',
  'arrow-function': 'var {name}{typeAnnotation} = {typeParams}({params}){returnType} => {body}',
  'function-expression': 'var {name}{typeAnnotation} = function{typeParams}({params}){returnType} {body}'
};

const UNNAMED_FUNCTION_TEMPLATES = {
  'function-expression': 'function{typeParams}({params}){returnType} {body}',
  'arrow-function': '{typeParams}({params}){returnType} => {body}'
};

const ERROR_MESSAGES = {
  'function-declaration': 'Function component is not a function declaration',
  'function-expression': 'Function component is not a function expression',
  'arrow-function': 'Function component is not an arrow function'
};

function hasOneUnconstrainedTypeParam(node) {
  if (node.typeParameters) {
    return node.typeParameters.params.length === 1 && !node.typeParameters.params[0].constraint;
  }

  return false;
}

function hasName(node) {
  return node.type === 'FunctionDeclaration' || node.parent.type === 'VariableDeclarator';
}

function getNodeText(prop, source) {
  if (!prop) return null;
  return source.slice(prop.range[0], prop.range[1]);
}

function getName(node) {
  if (node.type === 'FunctionDeclaration') {
    return node.id.name;
  }

  if (node.type === 'ArrowFunctionExpression' || node.type === 'FunctionExpression') {
    return hasName(node) && node.parent.id.name;
  }
}

function getParams(node, source) {
  if (node.params.length === 0) return null;
  return source.slice(node.params[0].range[0], node.params[node.params.length - 1].range[1]);
}

function getBody(node, source) {
  const range = node.body.range;

  if (node.body.type !== 'BlockStatement') {
    return [
      '{',
      `  return ${source.slice(range[0], range[1])}`,
      '}'
    ].join('\n');
  }

  return source.slice(range[0], range[1]);
}

function getTypeAnnotation(node, source) {
  if (!hasName(node) || node.type === 'FunctionDeclaration') return;

  if (node.type === 'ArrowFunctionExpression' || node.type === 'FunctionExpression') {
    return getNodeText(node.parent.id.typeAnnotation, source);
  }
}

function isUnfixableBecauseOfExport(node) {
  return node.type === 'FunctionDeclaration' && node.parent && node.parent.type === 'ExportDefaultDeclaration';
}

function isFunctionExpressionWithName(node) {
  return node.type === 'FunctionExpression' && node.id && node.id.name;
}

module.exports = {
  meta: {
    docs: {
      description: 'Standardize the way function component get defined',
      category: 'Stylistic Issues',
      recommended: false,
      url: docsUrl('function-component-definition')
    },
    fixable: 'code',

    schema: [{
      type: 'object',
      properties: {
        namedComponents: {
          enum: ['function-declaration', 'arrow-function', 'function-expression']
        },
        unnamedComponents: {
          enum: ['arrow-function', 'function-expression']
        }
      }
    }]
  },

  create: Components.detect((context, components) => {
    const configuration = context.options[0] || {};

    const namedConfig = configuration.namedComponents || 'function-declaration';
    const unnamedConfig = configuration.unnamedComponents || 'function-expression';

    function getFixer(node, options) {
      const sourceCode = context.getSourceCode();
      const source = sourceCode.getText();

      const typeAnnotation = getTypeAnnotation(node, source);

      if (options.type === 'function-declaration' && typeAnnotation) return;
      if (options.type === 'arrow-function' && hasOneUnconstrainedTypeParam(node)) return;
      if (isUnfixableBecauseOfExport(node)) return;
      if (isFunctionExpressionWithName(node)) return;

      return (fixer) => fixer.replaceTextRange(options.range, buildFunction(options.template, {
        typeAnnotation,
        typeParams: getNodeText(node.typeParameters, source),
        params: getParams(node, source),
        returnType: getNodeText(node.returnType, source),
        body: getBody(node, source),
        name: getName(node)
      }));
    }

    function report(node, options) {
      context.report({
        node,
        message: options.message,
        fix: getFixer(node, options.fixerOptions)
      });
    }

    function validate(node, functionType) {
      if (!components.get(node)) return;

      if (node.parent && node.parent.type === 'Property') return;

      if (hasName(node) && namedConfig !== functionType) {
        report(node, {
          message: ERROR_MESSAGES[namedConfig],
          fixerOptions: {
            type: namedConfig,
            template: NAMED_FUNCTION_TEMPLATES[namedConfig],
            range: node.type === 'FunctionDeclaration'
              ? node.range
              : node.parent.parent.range
          }
        });
      }
      if (!hasName(node) && unnamedConfig !== functionType) {
        report(node, {
          message: ERROR_MESSAGES[unnamedConfig],
          fixerOptions: {
            type: unnamedConfig,
            template: UNNAMED_FUNCTION_TEMPLATES[unnamedConfig],
            range: node.range
          }
        });
      }
    }

    // --------------------------------------------------------------------------
    // Public
    // --------------------------------------------------------------------------

    return {
      FunctionDeclaration(node) { validate(node, 'function-declaration'); },
      ArrowFunctionExpression(node) { validate(node, 'arrow-function'); },
      FunctionExpression(node) { validate(node, 'function-expression'); }
    };
  })
};
