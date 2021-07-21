/* global dom */

/**
 * Get all elements (including given node) that are part of the tab order
 * @method getTabbableElements
 * @memberof axe.commons.dom
 * @instance
 * @param  {Object} virtualNode The virtualNode to assess
 * @return {Boolean}
 */
dom.getTabbableElements = function getTabbableElements(virtualNode) {
	const nodeAndDescendents = axe.utils.querySelectorAll(virtualNode, '*');

	const tabbableElements = nodeAndDescendents.filter(vNode => {
		const isFocusable = vNode.isFocusable;
		let tabIndex = vNode.actualNode.getAttribute('tabindex');
		tabIndex =
			tabIndex && !isNaN(parseInt(tabIndex, 10)) ? parseInt(tabIndex) : null;

		return tabIndex ? isFocusable && tabIndex >= 0 : isFocusable;
	});

	return tabbableElements;
};
