/* global matches */

/**
 * Check if a virtual node matches some attribute(s)
 *
 * Note: matches.properties(vNode, matcher) can be indirectly used through
 * matches(vNode, { properties: matcher })
 *
 * Example:
 * ```js
 * matches.properties(vNode, {
 *   type: 'text', // Simple string match
 *   value: value => value.trim() !== '', // None-empty value, using a function matcher
 * })
 * ```
 *
 * @deprecated HTMLElement is deprecated, use VirtualNode instead
 *
 * @param {HTMLElement|VirtualNode} vNode
 * @param {Object} matcher
 * @returns {Boolean}
 */
matches.properties = function matchesProperties(vNode, matcher) {
	if (!(vNode instanceof axe.AbstractVirtualNode)) {
		vNode = axe.utils.getNodeFromTree(vNode);
	}
	return matches.fromFunction(propName => vNode.props[propName], matcher);
};
