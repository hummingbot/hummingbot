/* global forms */

/**
 * Determines if an element is an aria textbox element
 * @method isAriaTextbox
 * @memberof axe.commons.forms
 * @param {Element} node Node to determine if aria textbox
 * @returns {Bool}
 */
forms.isAriaTextbox = function(node) {
	const role = axe.commons.aria.getRole(node, { noImplicit: true });
	return role === 'textbox';
};
