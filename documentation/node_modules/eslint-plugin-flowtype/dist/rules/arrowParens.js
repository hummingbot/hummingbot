'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
var getLocation = function getLocation(node) {
  return {
    end: node.params[node.params.length - 1].loc.end,
    start: node.params[0].loc.start
  };
};

var isOpeningParenToken = function isOpeningParenToken(token) {
  return token.value === '(' && token.type === 'Punctuator';
};

var isClosingParenToken = function isClosingParenToken(token) {
  return token.value === ')' && token.type === 'Punctuator';
};

exports.default = {
  create(context) {
    var asNeeded = context.options[0] === 'as-needed';
    var requireForBlockBody = asNeeded && context.options[1] && context.options[1].requireForBlockBody === true;

    var sourceCode = context.getSourceCode();

    // Determines whether a arrow function argument end with `)`
    // eslint-disable-next-line complexity
    var parens = function parens(node) {
      var isAsync = node.async;
      var firstTokenOfParam = sourceCode.getFirstToken(node, isAsync ? 1 : 0);

      // Remove the parenthesis around a parameter
      var fixParamsWithParenthesis = function fixParamsWithParenthesis(fixer) {
        var paramToken = sourceCode.getTokenAfter(firstTokenOfParam);

        /*
         * ES8 allows Trailing commas in function parameter lists and calls
         * https://github.com/eslint/eslint/issues/8834
         */
        var closingParenToken = sourceCode.getTokenAfter(paramToken, isClosingParenToken);
        var asyncToken = isAsync ? sourceCode.getTokenBefore(firstTokenOfParam) : null;
        var shouldAddSpaceForAsync = asyncToken && asyncToken.range[1] === firstTokenOfParam.range[0];

        return fixer.replaceTextRange([firstTokenOfParam.range[0], closingParenToken.range[1]], `${shouldAddSpaceForAsync ? ' ' : ''}${paramToken.value}`);
      };

      // Type parameters without an opening paren is always a parse error, and
      // can therefore be safely ignored.
      if (node.typeParameters) {
        return;
      }

      // Similarly, a predicate always requires parens just like a return type
      // does, and therefore this case can also be safely ignored.
      if (node.predicate) {
        return;
      }

      // "as-needed", { "requireForBlockBody": true }: x => x
      if (requireForBlockBody && node.params.length === 1 && node.params[0].type === 'Identifier' && !node.params[0].typeAnnotation && node.body.type !== 'BlockStatement' && !node.returnType) {
        if (isOpeningParenToken(firstTokenOfParam)) {
          context.report({
            fix: fixParamsWithParenthesis,
            loc: getLocation(node),
            messageId: 'unexpectedParensInline',
            node
          });
        }

        return;
      }

      if (requireForBlockBody && node.body.type === 'BlockStatement') {
        if (!isOpeningParenToken(firstTokenOfParam)) {
          context.report({
            fix(fixer) {
              return fixer.replaceText(firstTokenOfParam, `(${firstTokenOfParam.value})`);
            },
            loc: getLocation(node),
            messageId: 'expectedParensBlock',
            node
          });
        }

        return;
      }

      // "as-needed": x => x
      if (asNeeded && node.params.length === 1 && node.params[0].type === 'Identifier' && !node.params[0].typeAnnotation && !node.returnType) {
        if (isOpeningParenToken(firstTokenOfParam)) {
          context.report({
            fix: fixParamsWithParenthesis,
            loc: getLocation(node),
            messageId: 'unexpectedParens',
            node
          });
        }

        return;
      }

      if (firstTokenOfParam.type === 'Identifier') {
        var after = sourceCode.getTokenAfter(firstTokenOfParam);

        // (x) => x
        if (after.value !== ')') {
          context.report({
            fix(fixer) {
              return fixer.replaceText(firstTokenOfParam, `(${firstTokenOfParam.value})`);
            },
            loc: getLocation(node),
            messageId: 'expectedParens',
            node
          });
        }
      }
    };

    return {
      ArrowFunctionExpression: parens
    };
  },

  meta: {
    docs: {
      category: 'ECMAScript 6',
      description: 'require parentheses around arrow function arguments',
      recommended: false,
      url: 'https://eslint.org/docs/rules/arrow-parens'
    },

    fixable: 'code',

    messages: {
      expectedParens: 'Expected parentheses around arrow function argument.',
      expectedParensBlock: 'Expected parentheses around arrow function argument having a body with curly braces.',

      unexpectedParens: 'Unexpected parentheses around single function argument.',
      unexpectedParensInline: 'Unexpected parentheses around single function argument having a body with no curly braces.'
    },

    type: 'layout'
  },

  schema: [{
    enum: ['always', 'as-needed']
  }, {
    additionalProperties: false,
    properties: {
      requireForBlockBody: {
        default: false,
        type: 'boolean'
      }
    },
    type: 'object'
  }]
};
module.exports = exports.default;