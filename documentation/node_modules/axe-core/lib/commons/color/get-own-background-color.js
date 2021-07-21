/* global color */

/**
 * Returns the non-alpha-blended background color of an element
 *
 * @method getOwnBackgroundColor
 * @memberof axe.commons.color
 *
 * @param {Object} elmStyle style of the element
 * @return {Color}
 */
color.getOwnBackgroundColor = function getOwnBackgroundColor(elmStyle) {
	const bgColor = new color.Color();
	bgColor.parseRgbString(elmStyle.getPropertyValue('background-color'));

	if (bgColor.alpha !== 0) {
		const opacity = elmStyle.getPropertyValue('opacity');
		bgColor.alpha = bgColor.alpha * opacity;
	}

	return bgColor;
};
