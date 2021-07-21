/* global aria */

/**
 * Get the text value of aria-label, if any
 *
 * @deprecated Do not use Element directly. Pass VirtualNode instead
 * @param {VirtualNode|Element} element
 * @return {string} ARIA label
 */
aria.arialabelText = function arialabelText(node) {
	if (node instanceof axe.AbstractVirtualNode === false) {
		if (node.nodeType !== 1) {
			return '';
		}
		node = axe.utils.getNodeFromTree(node);
	}
	return node.attr('aria-label') || '';
};
