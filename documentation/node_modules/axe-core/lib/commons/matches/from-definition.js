/* global matches */
const matchers = ['nodeName', 'attributes', 'properties', 'condition'];

/**
 * Check if a virtual node matches some definition
 *
 * Note: matches.fromDefinition(vNode, definition) can be indirectly used through
 * matches(vNode, definition)
 *
 * Example:
 * ```js
 * matches.fromDefinition(vNode, {
 *   nodeName: ['div', 'span']
 *   attributes: {
 *     'aria-live': 'assertive'
 *   }
 * })
 * ```
 *
 * @deprecated HTMLElement is deprecated, use VirtualNode instead
 *
 * @private
 * @param {HTMLElement|VirtualNode} vNode
 * @param {Object|Array<Object>} definition
 * @returns {Boolean}
 */
matches.fromDefinition = function matchFromDefinition(vNode, definition) {
	if (!(vNode instanceof axe.AbstractVirtualNode)) {
		vNode = axe.utils.getNodeFromTree(vNode);
	}

	if (Array.isArray(definition)) {
		return definition.some(definitionItem => matches(vNode, definitionItem));
	}
	if (typeof definition === 'string') {
		return axe.utils.matches(vNode, definition);
	}

	return Object.keys(definition).every(matcherName => {
		if (!matchers.includes(matcherName)) {
			throw new Error(`Unknown matcher type "${matcherName}"`);
		}
		// Find the specific matches method to.
		// matches.attributes, matches.nodeName, matches.properties, etc.
		const matchMethod = matches[matcherName];

		// Find the matcher that goes into the matches method.
		// 'div', /^div$/, (str) => str === 'div', etc.
		const matcher = definition[matcherName];
		return matchMethod(vNode, matcher);
	});
};
