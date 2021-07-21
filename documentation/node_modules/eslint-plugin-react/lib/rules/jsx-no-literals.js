/**
 * @fileoverview Prevent using string literals in React component definition
 * @author Caleb Morris
 * @author David Buchan-Swanson
 */

'use strict';

const docsUrl = require('../util/docsUrl');

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

function trimIfString(val) {
  return typeof val === 'string' ? val.trim() : val;
}

module.exports = {
  meta: {
    docs: {
      description: 'Prevent using string literals in React component definition',
      category: 'Stylistic Issues',
      recommended: false,
      url: docsUrl('jsx-no-literals')
    },

    schema: [{
      type: 'object',
      properties: {
        noStrings: {
          type: 'boolean'
        },
        allowedStrings: {
          type: 'array',
          uniqueItems: true,
          items: {
            type: 'string'
          }
        },
        ignoreProps: {
          type: 'boolean'
        },
        noAttributeStrings: {
          type: 'boolean'
        }
      },
      additionalProperties: false
    }]
  },

  create(context) {
    const defaults = {
      noStrings: false,
      allowedStrings: [],
      ignoreProps: false,
      noAttributeStrings: false
    };
    const config = Object.assign({}, defaults, context.options[0] || {});
    config.allowedStrings = new Set(config.allowedStrings.map(trimIfString));

    function defaultMessage() {
      if (config.noAttributeStrings) {
        return 'Strings not allowed in attributes';
      }
      if (config.noStrings) {
        return 'Strings not allowed in JSX files';
      }
      return 'Missing JSX expression container around literal string';
    }

    function reportLiteralNode(node, customMessage) {
      const errorMessage = customMessage || defaultMessage();

      context.report({
        node,
        message: `${errorMessage}: “${context.getSourceCode().getText(node).trim()}”`
      });
    }

    function getParentIgnoringBinaryExpressions(node) {
      let current = node;
      while (current.parent.type === 'BinaryExpression') {
        current = current.parent;
      }
      return current.parent;
    }

    function getValidation(node) {
      if (config.allowedStrings.has(trimIfString(node.value))) {
        return false;
      }
      const parent = getParentIgnoringBinaryExpressions(node);

      function isParentNodeStandard() {
        if (!/^[\s]+$/.test(node.value) && typeof node.value === 'string' && parent.type.includes('JSX')) {
          if (config.noAttributeStrings) {
            return parent.type === 'JSXAttribute';
          }
          if (!config.noAttributeStrings) {
            return parent.type !== 'JSXAttribute';
          }
        }

        return false;
      }

      const standard = isParentNodeStandard();

      if (config.noStrings) {
        return standard;
      }
      return standard && parent.type !== 'JSXExpressionContainer';
    }

    function getParentAndGrandParentType(node) {
      const parent = getParentIgnoringBinaryExpressions(node);
      const parentType = parent.type;
      const grandParentType = parent.parent.type;

      return {
        parent,
        parentType,
        grandParentType,
        grandParent: parent.parent
      };
    }

    function hasJSXElementParentOrGrandParent(node) {
      const parents = getParentAndGrandParentType(node);
      const parentType = parents.parentType;
      const grandParentType = parents.grandParentType;

      return parentType === 'JSXFragment' || parentType === 'JSXElement' || grandParentType === 'JSXElement';
    }

    // --------------------------------------------------------------------------
    // Public
    // --------------------------------------------------------------------------

    return {
      Literal(node) {
        if (getValidation(node) && (hasJSXElementParentOrGrandParent(node) || !config.ignoreProps)) {
          reportLiteralNode(node);
        }
      },

      JSXAttribute(node) {
        const isNodeValueString = node && node.value && node.value.type === 'Literal' && typeof node.value.value === 'string' && !config.allowedStrings.has(node.value.value);

        if (config.noStrings && !config.ignoreProps && isNodeValueString) {
          const customMessage = 'Invalid prop value';
          reportLiteralNode(node, customMessage);
        }
      },

      JSXText(node) {
        if (getValidation(node)) {
          reportLiteralNode(node);
        }
      },

      TemplateLiteral(node) {
        const parents = getParentAndGrandParentType(node);
        const parentType = parents.parentType;
        const grandParentType = parents.grandParentType;
        const isParentJSXExpressionCont = parentType === 'JSXExpressionContainer';
        const isParentJSXElement = parentType === 'JSXElement' || grandParentType === 'JSXElement';

        if (isParentJSXExpressionCont && config.noStrings && (isParentJSXElement || !config.ignoreProps)) {
          reportLiteralNode(node);
        }
      }
    };
  }
};
