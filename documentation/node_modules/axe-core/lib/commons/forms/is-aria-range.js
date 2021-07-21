/* global forms */
const rangeRoles = ['progressbar', 'scrollbar', 'slider', 'spinbutton'];

/**
 * Determines if an element is an aria range element
 * @method isAriaRange
 * @memberof axe.commons.forms
 * @param {Element} node Node to determine if aria range
 * @returns {Bool}
 */
forms.isAriaRange = function(node) {
	const role = axe.commons.aria.getRole(node, { noImplicit: true });
	return rangeRoles.includes(role);
};
