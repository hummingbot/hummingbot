/* global dom */

/**
 * Reduce an array of elements to only those that are below a 'floating' element.
 * @method reduceToElementsBelowFloating
 * @memberof axe.commons.dom
 * @instance
 * @param {Array} elements
 * @param {Element} targetNode
 * @returns {Array}
 */
dom.reduceToElementsBelowFloating = function(elements, targetNode) {
	var floatingPositions = ['fixed', 'sticky'],
		finalElements = [],
		targetFound = false,
		index,
		currentNode,
		style;

	// Filter out elements that are temporarily floating above the target
	for (index = 0; index < elements.length; ++index) {
		currentNode = elements[index];
		if (currentNode === targetNode) {
			targetFound = true;
		}

		style = window.getComputedStyle(currentNode);

		if (!targetFound && floatingPositions.indexOf(style.position) !== -1) {
			//Target was not found yet, so it must be under this floating thing (and will not always be under it)
			finalElements = [];
			continue;
		}

		finalElements.push(currentNode);
	}

	return finalElements;
};
