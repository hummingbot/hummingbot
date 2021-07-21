/* global forms */

/**
 * Determines if an element is an aria combobox element
 * @method isAriaCombobox
 * @memberof axe.commons.forms
 * @param {Element} node Node to determine if aria combobox
 * @returns {Bool}
 */
forms.isAriaCombobox = function(node) {
	const role = axe.commons.aria.getRole(node, { noImplicit: true });
	return role === 'combobox';
};
