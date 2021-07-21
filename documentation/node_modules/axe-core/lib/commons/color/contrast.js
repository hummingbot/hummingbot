/* global color */

/**
 * @class Color
 * @memberof axe.commons.color
 * @param {number} red
 * @param {number} green
 * @param {number} blue
 * @param {number} alpha
 */
color.Color = function(red, green, blue, alpha) {
	/** @type {number} */
	this.red = red;

	/** @type {number} */
	this.green = green;

	/** @type {number} */
	this.blue = blue;

	/** @type {number} */
	this.alpha = alpha;

	/**
	 * Provide the hex string value for the color
	 * @method toHexString
	 * @memberof axe.commons.color.Color
	 * @instance
	 * @return {string}
	 */
	this.toHexString = function() {
		var redString = Math.round(this.red).toString(16);
		var greenString = Math.round(this.green).toString(16);
		var blueString = Math.round(this.blue).toString(16);
		return (
			'#' +
			(this.red > 15.5 ? redString : '0' + redString) +
			(this.green > 15.5 ? greenString : '0' + greenString) +
			(this.blue > 15.5 ? blueString : '0' + blueString)
		);
	};

	var rgbRegex = /^rgb\((\d+), (\d+), (\d+)\)$/;
	var rgbaRegex = /^rgba\((\d+), (\d+), (\d+), (\d*(\.\d+)?)\)/;

	/**
	 * Set the color value based on a CSS RGB/RGBA string
	 * @method parseRgbString
	 * @memberof axe.commons.color.Color
	 * @instance
	 * @param  {string}  rgb  The string value
	 */
	this.parseRgbString = function(colorString) {
		// IE can pass transparent as value instead of rgba
		if (colorString === 'transparent') {
			this.red = 0;
			this.green = 0;
			this.blue = 0;
			this.alpha = 0;
			return;
		}
		var match = colorString.match(rgbRegex);

		if (match) {
			this.red = parseInt(match[1], 10);
			this.green = parseInt(match[2], 10);
			this.blue = parseInt(match[3], 10);
			this.alpha = 1;
			return;
		}

		match = colorString.match(rgbaRegex);
		if (match) {
			this.red = parseInt(match[1], 10);
			this.green = parseInt(match[2], 10);
			this.blue = parseInt(match[3], 10);

			// alpha values can be between 0 and 1, with browsers having
			// different floating point precision. for example,
			// 'rgba(0,0,0,0.5)' results in 'rgba(0,0,0,0.498039)' in Safari
			// when getting the computed style background-color property. to
			// fix this, we'll round all alpha values to 2 decimal points.
			this.alpha = Math.round(parseFloat(match[4]) * 100) / 100;
			return;
		}
	};

	/**
	 * Get the relative luminance value
	 * using algorithm from http://www.w3.org/WAI/GL/wiki/Relative_luminance
	 * @method getRelativeLuminance
	 * @memberof axe.commons.color.Color
	 * @instance
	 * @return {number} The luminance value, ranges from 0 to 1
	 */
	this.getRelativeLuminance = function() {
		var rSRGB = this.red / 255;
		var gSRGB = this.green / 255;
		var bSRGB = this.blue / 255;

		var r =
			rSRGB <= 0.03928 ? rSRGB / 12.92 : Math.pow((rSRGB + 0.055) / 1.055, 2.4);
		var g =
			gSRGB <= 0.03928 ? gSRGB / 12.92 : Math.pow((gSRGB + 0.055) / 1.055, 2.4);
		var b =
			bSRGB <= 0.03928 ? bSRGB / 12.92 : Math.pow((bSRGB + 0.055) / 1.055, 2.4);

		return 0.2126 * r + 0.7152 * g + 0.0722 * b;
	};
};

/**
 * Combine the two given color according to alpha blending.
 * @method flattenColors
 * @memberof axe.commons.color.Color
 * @instance
 * @param {Color} fgColor Foreground color
 * @param {Color} bgColor Background color
 * @return {Color} Blended color
 */
color.flattenColors = function(fgColor, bgColor) {
	var alpha = fgColor.alpha;
	var r = (1 - alpha) * bgColor.red + alpha * fgColor.red;
	var g = (1 - alpha) * bgColor.green + alpha * fgColor.green;
	var b = (1 - alpha) * bgColor.blue + alpha * fgColor.blue;
	var a = fgColor.alpha + bgColor.alpha * (1 - fgColor.alpha);

	return new color.Color(r, g, b, a);
};

/**
 * Get the contrast of two colors
 * @method getContrast
 * @memberof axe.commons.color.Color
 * @instance
 * @param  {Color}  bgcolor  Background color
 * @param  {Color}  fgcolor  Foreground color
 * @return {number} The contrast ratio
 */
color.getContrast = function(bgColor, fgColor) {
	if (!fgColor || !bgColor) {
		return null;
	}

	if (fgColor.alpha < 1) {
		fgColor = color.flattenColors(fgColor, bgColor);
	}

	var bL = bgColor.getRelativeLuminance();
	var fL = fgColor.getRelativeLuminance();

	return (Math.max(fL, bL) + 0.05) / (Math.min(fL, bL) + 0.05);
};

/**
 * Check whether certain text properties meet WCAG contrast rules
 * @method hasValidContrastRatio
 * @memberof axe.commons.color.Color
 * @instance
 * @param  {Color}  bgcolor  Background color
 * @param  {Color}  fgcolor  Foreground color
 * @param  {number}  fontSize  Font size of text, in pixels
 * @param  {boolean}  isBold  Whether the text is bold
 * @return {{isValid: boolean, contrastRatio: number, expectedContrastRatio: number}}
 */
color.hasValidContrastRatio = function(bg, fg, fontSize, isBold) {
	var contrast = color.getContrast(bg, fg);
	var isSmallFont =
		(isBold && Math.ceil(fontSize * 72) / 96 < 14) ||
		(!isBold && Math.ceil(fontSize * 72) / 96 < 18);
	var expectedContrastRatio = isSmallFont ? 4.5 : 3;

	return {
		isValid: contrast > expectedContrastRatio,
		contrastRatio: contrast,
		expectedContrastRatio: expectedContrastRatio
	};
};
