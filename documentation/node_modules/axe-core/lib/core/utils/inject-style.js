/*exported injectStyle */
/*global axe*/

var styleSheet;
function injectStyle(style) {
	'use strict';

	if (styleSheet && styleSheet.parentNode) {
		// append the style to the existing sheet
		if (styleSheet.styleSheet === undefined) {
			// Not old IE
			styleSheet.appendChild(document.createTextNode(style));
		} else {
			styleSheet.styleSheet.cssText += style;
		}
		return styleSheet;
	}
	if (!style) {
		return;
	}

	var head = document.head || document.getElementsByTagName('head')[0];
	styleSheet = document.createElement('style');
	styleSheet.type = 'text/css';

	if (styleSheet.styleSheet === undefined) {
		// Not old IE
		styleSheet.appendChild(document.createTextNode(style));
	} else {
		styleSheet.styleSheet.cssText = style;
	}

	head.appendChild(styleSheet);

	return styleSheet;
}

axe.utils.injectStyle = injectStyle;
