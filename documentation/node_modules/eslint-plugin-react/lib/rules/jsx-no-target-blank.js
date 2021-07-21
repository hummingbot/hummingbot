/**
 * @fileoverview Forbid target='_blank' attribute
 * @author Kevin Miller
 */

'use strict';

const docsUrl = require('../util/docsUrl');
const linkComponentsUtil = require('../util/linkComponents');

// ------------------------------------------------------------------------------
// Rule Definition
// ------------------------------------------------------------------------------

function isTargetBlank(attr) {
  return attr.name
    && attr.name.name === 'target'
    && attr.value
    && ((
      attr.value.type === 'Literal'
      && attr.value.value.toLowerCase() === '_blank'
    ) || (
      attr.value.type === 'JSXExpressionContainer'
      && attr.value.expression
      && attr.value.expression.value
      && attr.value.expression.value.toLowerCase() === '_blank'
    ));
}

function hasExternalLink(element, linkAttribute) {
  return element.attributes.some((attr) => attr.name
      && attr.name.name === linkAttribute
      && attr.value.type === 'Literal'
      && /^(?:\w+:|\/\/)/.test(attr.value.value));
}

function hasDynamicLink(element, linkAttribute) {
  return element.attributes.some((attr) => attr.name
    && attr.name.name === linkAttribute
    && attr.value.type === 'JSXExpressionContainer');
}

function hasSecureRel(element, allowReferrer) {
  return element.attributes.find((attr) => {
    if (attr.type === 'JSXAttribute' && attr.name.name === 'rel') {
      const value = attr.value
        && ((
          attr.value.type === 'Literal'
          && attr.value.value
        ) || (
          attr.value.type === 'JSXExpressionContainer'
          && attr.value.expression
          && attr.value.expression.value
        ));
      const tags = value && value.toLowerCase && value.toLowerCase().split(' ');
      return tags && (allowReferrer ? tags.indexOf('noopener') >= 0 : tags.indexOf('noreferrer') >= 0);
    }
    return false;
  });
}

module.exports = {
  meta: {
    docs: {
      description: 'Forbid `target="_blank"` attribute without `rel="noreferrer"`',
      category: 'Best Practices',
      recommended: true,
      url: docsUrl('jsx-no-target-blank')
    },
    schema: [{
      type: 'object',
      properties: {
        allowReferrer: {
          type: 'boolean'
        },
        enforceDynamicLinks: {
          enum: ['always', 'never']
        }
      },
      additionalProperties: false
    }]
  },

  create(context) {
    const configuration = context.options[0] || {};
    const allowReferrer = configuration.allowReferrer || false;
    const enforceDynamicLinks = configuration.enforceDynamicLinks || 'always';
    const components = linkComponentsUtil.getLinkComponents(context);

    return {
      JSXAttribute(node) {
        if (
          !components.has(node.parent.name.name)
          || !isTargetBlank(node)
          || hasSecureRel(node.parent, allowReferrer)
        ) {
          return;
        }

        const linkAttribute = components.get(node.parent.name.name);

        if (hasExternalLink(node.parent, linkAttribute) || (enforceDynamicLinks === 'always' && hasDynamicLink(node.parent, linkAttribute))) {
          context.report({
            node,
            message: 'Using target="_blank" without rel="noreferrer" '
              + 'is a security risk: see https://html.spec.whatwg.org/multipage/links.html#link-type-noopener'
          });
        }
      }
    };
  }
};
