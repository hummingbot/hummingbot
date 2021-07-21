/**
 * @fileoverview Restrict file extensions that may contain JSX
 * @author Joe Lencioni
 */

'use strict';

const path = require('path');
const docsUrl = require('../util/docsUrl');

// ------------------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------------------

const DEFAULTS = {
  allow: 'always',
  extensions: ['.jsx']
};

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

module.exports = {
  meta: {
    docs: {
      description: 'Restrict file extensions that may contain JSX',
      category: 'Stylistic Issues',
      recommended: false,
      url: docsUrl('jsx-filename-extension')
    },

    schema: [{
      type: 'object',
      properties: {
        allow: {
          enum: ['always', 'as-needed']
        },
        extensions: {
          type: 'array',
          items: {
            type: 'string'
          }
        }
      },
      additionalProperties: false
    }]
  },

  create(context) {
    const filename = context.getFilename();

    let jsxNode;

    if (filename === '<text>') {
      // No need to traverse any nodes.
      return {};
    }

    const allow = (context.options[0] && context.options[0].allow) || DEFAULTS.allow;
    const allowedExtensions = (context.options[0] && context.options[0].extensions) || DEFAULTS.extensions;
    const isAllowedExtension = allowedExtensions.some((extension) => filename.slice(-extension.length) === extension);

    function handleJSX(node) {
      if (!jsxNode) {
        jsxNode = node;
      }
    }

    // --------------------------------------------------------------------------
    // Public
    // --------------------------------------------------------------------------

    return {
      JSXElement: handleJSX,
      JSXFragment: handleJSX,

      'Program:exit'(node) {
        if (jsxNode) {
          if (!isAllowedExtension) {
            context.report({
              node: jsxNode,
              message: `JSX not allowed in files with extension '${path.extname(filename)}'`
            });
          }
          return;
        }

        if (isAllowedExtension && allow === 'as-needed') {
          context.report({
            node,
            message: `Only files containing JSX may use the extension '${path.extname(filename)}'`
          });
        }
      }
    };
  }
};
