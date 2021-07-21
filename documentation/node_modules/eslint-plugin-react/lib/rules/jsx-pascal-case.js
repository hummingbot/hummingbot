/**
 * @fileoverview Enforce PascalCase for user-defined JSX components
 * @author Jake Marsh
 */

'use strict';

const elementType = require('jsx-ast-utils/elementType');
const docsUrl = require('../util/docsUrl');
const jsxUtil = require('../util/jsx');

function testDigit(char) {
  const charCode = char.charCodeAt(0);
  return charCode >= 48 && charCode <= 57;
}

function testUpperCase(char) {
  const upperCase = char.toUpperCase();
  return char === upperCase && upperCase !== char.toLowerCase();
}

function testLowerCase(char) {
  const lowerCase = char.toLowerCase();
  return char === lowerCase && lowerCase !== char.toUpperCase();
}

function testPascalCase(name) {
  if (!testUpperCase(name.charAt(0))) {
    return false;
  }
  const anyNonAlphaNumeric = Array.prototype.some.call(
    name.slice(1),
    (char) => char.toLowerCase() === char.toUpperCase() && !testDigit(char)
  );
  if (anyNonAlphaNumeric) {
    return false;
  }
  return Array.prototype.some.call(
    name.slice(1),
    (char) => testLowerCase(char) || testDigit(char)
  );
}

function testAllCaps(name) {
  const firstChar = name.charAt(0);
  if (!(testUpperCase(firstChar) || testDigit(firstChar))) {
    return false;
  }
  for (let i = 1; i < name.length - 1; i += 1) {
    const char = name.charAt(i);
    if (!(testUpperCase(char) || testDigit(char) || char === '_')) {
      return false;
    }
  }
  const lastChar = name.charAt(name.length - 1);
  if (!(testUpperCase(lastChar) || testDigit(lastChar))) {
    return false;
  }
  return true;
}

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

module.exports = {
  meta: {
    docs: {
      description: 'Enforce PascalCase for user-defined JSX components',
      category: 'Stylistic Issues',
      recommended: false,
      url: docsUrl('jsx-pascal-case')
    },

    schema: [{
      type: 'object',
      properties: {
        allowAllCaps: {
          type: 'boolean'
        },
        ignore: {
          type: 'array'
        }
      },
      additionalProperties: false
    }]
  },

  create(context) {
    const configuration = context.options[0] || {};
    const allowAllCaps = configuration.allowAllCaps || false;
    const ignore = configuration.ignore || [];

    return {
      JSXOpeningElement(node) {
        const isCompatTag = jsxUtil.isDOMComponent(node);
        if (isCompatTag) return undefined;

        let name = elementType(node);

        // Get JSXIdentifier if the type is JSXNamespacedName or JSXMemberExpression
        if (name.lastIndexOf(':') > -1) {
          name = name.substring(name.lastIndexOf(':') + 1);
        } else if (name.lastIndexOf('.') > -1) {
          name = name.substring(name.lastIndexOf('.') + 1);
        }

        if (name.length === 1) return undefined;

        const isPascalCase = testPascalCase(name);
        const isAllowedAllCaps = allowAllCaps && testAllCaps(name);
        const isIgnored = ignore.indexOf(name) !== -1;

        if (!isPascalCase && !isAllowedAllCaps && !isIgnored) {
          let message = `Imported JSX component ${name} must be in PascalCase`;

          if (allowAllCaps) {
            message += ' or SCREAMING_SNAKE_CASE';
          }

          context.report({node, message});
        }
      }
    };
  }
};
