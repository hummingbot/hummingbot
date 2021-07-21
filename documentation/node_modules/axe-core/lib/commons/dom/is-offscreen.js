/* global dom */

function noParentScrolled(element, offset) {
	element = dom.getComposedParent(element);
	while (element && element.nodeName.toLowerCase() !== 'html') {
		if (element.scrollTop) {
			offset += element.scrollTop;
			if (offset >= 0) {
				return false;
			}
		}
		element = dom.getComposedParent(element);
	}
	return true;
}

/**
 * Determines if element is off screen
 * @method isOffscreen
 * @memberof axe.commons.dom
 * @instance
 * @param  {Element} element
 * @return {Boolean}
 */
dom.isOffscreen = function(element) {
	let leftBoundary;
	const docElement = document.documentElement;
	const styl = window.getComputedStyle(element);
	const dir = window
		.getComputedStyle(document.body || docElement)
		.getPropertyValue('direction');
	const coords = dom.getElementCoordinates(element);

	// bottom edge beyond
	if (
		coords.bottom < 0 &&
		(noParentScrolled(element, coords.bottom) || styl.position === 'absolute')
	) {
		return true;
	}

	if (coords.left === 0 && coords.right === 0) {
		//This is an edge case, an empty (zero-width) element that isn't positioned 'off screen'.
		return false;
	}

	if (dir === 'ltr') {
		if (coords.right <= 0) {
			return true;
		}
	} else {
		leftBoundary = Math.max(
			docElement.scrollWidth,
			dom.getViewportSize(window).width
		);
		if (coords.left >= leftBoundary) {
			return true;
		}
	}

	return false;
};
