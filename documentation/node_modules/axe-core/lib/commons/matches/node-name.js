/* global matches */
/**
 * Check if the nodeName of a virtual node matches some value.
 *
 * Note: matches.nodeName(vNode, matcher) can be indirectly used through
 * matches(vNode, { nodeName: matcher })
 *
 * Example:
 * ```js
 * matches.nodeName(vNode, ['div', 'span'])
 * ```
 *
 * @deprecated HTMLElement is deprecated, use VirtualNode instead
 *
 * @param {HTMLElement|VirtualNode} vNode
 * @param {Object} Attribute matcher
 * @returns {Boolean}
 */
matches.nodeName = function matchNodeName(vNode, matcher) {
	if (!(vNode instanceof axe.AbstractVirtualNode)) {
		vNode = axe.utils.getNodeFromTree(vNode);
	}
	return matches.fromPrimative(vNode.props.nodeName, matcher);
};
