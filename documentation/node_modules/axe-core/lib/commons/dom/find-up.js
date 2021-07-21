/* global dom, axe */
/**
 * Find the virtual node and call dom.fundUpVirtual
 *
 * **WARNING:** this should be used sparingly, as it's not even close to being performant
 * @method findUp
 * @memberof axe.commons.dom
 * @instance
 * @param {HTMLElement} element The starting HTMLElement
 * @param {String} target The selector for the HTMLElement
 * @return {HTMLElement|null} Either the matching HTMLElement or `null` if there was no match
 */
dom.findUp = function(element, target) {
	return dom.findUpVirtual(axe.utils.getNodeFromTree(element), target);
};

/**
 * recusively walk up the DOM, checking for a node which matches a selector
 *
 * **WARNING:** this should be used sparingly, as it's not even close to being performant
 * @method findUpVirtual
 * @memberof axe.commons.dom
 * @instance
 * @param {VirtualNode} element The starting virtualNode
 * @param {String} target The selector for the HTMLElement
 * @return {HTMLElement|null} Either the matching HTMLElement or `null` if there was no match
 */
dom.findUpVirtual = function(element, target) {
	let parent;

	parent = element.actualNode;
	// virtualNode will have a shadowId if the element lives inside a shadow DOM or is
	// slotted into a shadow DOM
	if (!element.shadowId && typeof element.actualNode.closest === 'function') {
		// non-shadow DOM elements
		let match = element.actualNode.closest(target);
		if (match) {
			return match;
		}
		return null;
	}
	// handle shadow DOM elements and older browsers
	do {
		// recursively walk up the DOM, checking each parent node
		parent = parent.assignedSlot ? parent.assignedSlot : parent.parentNode;
		if (parent && parent.nodeType === 11) {
			parent = parent.host;
		}
	} while (
		parent &&
		!axe.utils.matchesSelector(parent, target) &&
		parent !== document.documentElement
	);

	if (!parent) {
		return null;
	}

	if (!axe.utils.matchesSelector(parent, target)) {
		return null;
	}
	return parent;
};
