/* global matches */
/**
 * Check if a virtual node matches some attribute(s)
 *
 * Note: matches.attributes(vNode, matcher) can be indirectly used through
 * matches(vNode, { attributes: matcher })
 *
 * Example:
 * ```js
 * matches.attributes(vNode, {
 *   'aria-live': 'assertive', // Simple string match
 *   'aria-expanded': /true|false/i, // either boolean, case insensitive
 * })
 * ```
 *
 * @deprecated HTMLElement is deprecated, use VirtualNode instead
 *
 * @param {HTMLElement|VirtualNode} vNode
 * @param {Object} Attribute matcher
 * @returns {Boolean}
 */
matches.attributes = function matchesAttributes(vNode, matcher) {
	if (!(vNode instanceof axe.AbstractVirtualNode)) {
		vNode = axe.utils.getNodeFromTree(vNode);
	}
	return matches.fromFunction(attrName => vNode.attr(attrName), matcher);
};
