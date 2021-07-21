/**
 * @fileoverview Disallow multiple spaces between inline JSX props
 * @author Adrian Moennich
 */

'use strict';

const docsUrl = require('../util/docsUrl');

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

module.exports = {
  meta: {
    docs: {
      description: 'Disallow multiple spaces between inline JSX props',
      category: 'Stylistic Issues',
      recommended: false,
      url: docsUrl('jsx-props-no-multi-spaces')
    },
    fixable: 'code',
    schema: []
  },

  create(context) {
    const sourceCode = context.getSourceCode();

    function getPropName(propNode) {
      switch (propNode.type) {
        case 'JSXSpreadAttribute':
          return context.getSourceCode().getText(propNode.argument);
        case 'JSXIdentifier':
          return propNode.name;
        case 'JSXMemberExpression':
          return `${getPropName(propNode.object)}.${propNode.property.name}`;
        default:
          return propNode.name.name;
      }
    }

    function hasEmptyLines(node, leadingLineCount) {
      const allComments = sourceCode.getCommentsBefore(node);
      let commentLines = 0;

      if (allComments.length > 0) {
        allComments.forEach((comment) => {
          const start = comment.loc.start.line;
          const end = comment.loc.end.line;

          commentLines += (end - start + 1);
        });

        return commentLines !== leadingLineCount;
      }

      return true;
    }

    function checkSpacing(prev, node) {
      const prevNodeEndLine = prev.loc.end.line;
      const currNodeStartLine = node.loc.start.line;
      const leadingLineCount = currNodeStartLine - prevNodeEndLine - 1;

      if (leadingLineCount > 0 && hasEmptyLines(node, leadingLineCount)) {
        context.report({
          node,
          message: `Expected no line gap between “${getPropName(prev)}” and “${getPropName(node)}”`
        });
      }

      if (prev.loc.end.line !== node.loc.end.line) {
        return;
      }

      const between = context.getSourceCode().text.slice(prev.range[1], node.range[0]);

      if (between !== ' ') {
        context.report({
          node,
          message: `Expected only one space between "${getPropName(prev)}" and "${getPropName(node)}"`,
          fix(fixer) {
            return fixer.replaceTextRange([prev.range[1], node.range[0]], ' ');
          }
        });
      }
    }

    function containsGenericType(node) {
      const containsTypeParams = typeof node.typeParameters !== 'undefined';
      return containsTypeParams && node.typeParameters.type === 'TSTypeParameterInstantiation';
    }

    function getGenericNode(node) {
      const name = node.name;
      if (containsGenericType(node)) {
        const type = node.typeParameters;

        return Object.assign(
          {},
          node,
          {
            range: [
              name.range[0],
              type.range[1]
            ]
          }
        );
      }

      return name;
    }

    return {
      JSXOpeningElement(node) {
        node.attributes.reduce((prev, prop) => {
          checkSpacing(prev, prop);
          return prop;
        }, getGenericNode(node));
      }
    };
  }
};
