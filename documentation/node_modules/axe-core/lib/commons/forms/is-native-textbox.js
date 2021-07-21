/* global forms */
const nonTextInputTypes = [
	'button',
	'checkbox',
	'color',
	'file',
	'hidden',
	'image',
	'password',
	'radio',
	'reset',
	'submit'
];

/**
 * Determines if an element is a native textbox element
 * @method isNativeTextbox
 * @memberof axe.commons.forms
 * @param {Element} node Node to determine if textbox
 * @returns {Bool}
 */
forms.isNativeTextbox = function(node) {
	const nodeName = node.nodeName.toUpperCase();
	return (
		nodeName === 'TEXTAREA' ||
		(nodeName === 'INPUT' && !nonTextInputTypes.includes(node.type))
	);
};
