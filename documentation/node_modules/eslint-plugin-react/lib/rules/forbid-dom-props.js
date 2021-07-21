/**
 * @fileoverview Forbid certain props on DOM Nodes
 * @author David Vázquez
 */

'use strict';

const docsUrl = require('../util/docsUrl');

// ------------------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------------------

const DEFAULTS = [];

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

module.exports = {
  meta: {
    docs: {
      description: 'Forbid certain props on DOM Nodes',
      category: 'Best Practices',
      recommended: false,
      url: docsUrl('forbid-dom-props')
    },

    schema: [{
      type: 'object',
      properties: {
        forbid: {
          type: 'array',
          items: {
            oneOf: [{
              type: 'string'
            }, {
              type: 'object',
              properties: {
                propName: {
                  type: 'string'
                },
                message: {
                  type: 'string'
                }
              }
            }],
            minLength: 1
          },
          uniqueItems: true
        }
      },
      additionalProperties: false
    }]
  },

  create(context) {
    const configuration = context.options[0] || {};
    const forbid = new Map((configuration.forbid || DEFAULTS).map((value) => {
      const propName = typeof value === 'string' ? value : value.propName;
      const options = {
        message: typeof value === 'string' ? null : value.message
      };
      return [propName, options];
    }));

    function isForbidden(prop) {
      return forbid.has(prop);
    }

    return {
      JSXAttribute(node) {
        const tag = node.parent.name.name;
        if (!(tag && tag[0] !== tag[0].toUpperCase())) {
          // This is a Component, not  a DOM node, so exit.
          return;
        }

        const prop = node.name.name;

        if (!isForbidden(prop)) {
          return;
        }

        const customMessage = forbid.get(prop).message;
        const errorMessage = customMessage || `Prop \`${prop}\` is forbidden on DOM Nodes`;

        context.report({
          node,
          message: errorMessage
        });
      }
    };
  }
};
