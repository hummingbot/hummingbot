/* global text, aria, dom */
const controlValueRoles = [
	'textbox',
	'progressbar',
	'scrollbar',
	'slider',
	'spinbutton',
	'combobox',
	'listbox'
];

text.formControlValueMethods = {
	nativeTextboxValue,
	nativeSelectValue,
	ariaTextboxValue,
	ariaListboxValue,
	ariaComboboxValue,
	ariaRangeValue
};

/**
 * Calculate value of a form control
 *
 * @param {VirtualNode} element The VirtualNode instance whose value we want
 * @param {Object} context
 * @property {Element} startNode First node in accessible name computation
 * @property {String[]} unsupported List of roles where value computation is unsupported
 * @property {Bool} debug Enable logging for formControlValue
 * @return {string} The calculated value
 */
text.formControlValue = function formControlValue(virtualNode, context = {}) {
	const { actualNode } = virtualNode;
	const unsupported = text.unsupported.accessibleNameFromFieldValue || [];
	const role = aria.getRole(actualNode);

	if (
		// For the targeted node, the accessible name is never the value:
		context.startNode === virtualNode ||
		// Only elements with a certain role can return their value
		!controlValueRoles.includes(role) ||
		// Skip unsupported roles
		unsupported.includes(role)
	) {
		return '';
	}

	// Object.values:
	const valueMethods = Object.keys(text.formControlValueMethods).map(
		name => text.formControlValueMethods[name]
	);

	// Return the value of the first step that returns with text
	let valueString = valueMethods.reduce((accName, step) => {
		return accName || step(virtualNode, context);
	}, '');

	if (context.debug) {
		axe.log(valueString || '{empty-value}', actualNode, context);
	}
	return valueString;
};

/**
 * Calculate value of a native textbox element (input and textarea)
 *
 * @param {VirtualNode|Element} element The element whose value we want
 * @return {string} The calculated value
 */
function nativeTextboxValue(node) {
	node = node.actualNode || node;
	if (axe.commons.forms.isNativeTextbox(node)) {
		return node.value || '';
	}
	return '';
}

/**
 * Calculate value of a select element
 *
 * @param {VirtualNode} element The VirtualNode instance whose value we want
 * @return {string} The calculated value
 */
function nativeSelectValue(node) {
	node = node.actualNode || node;
	if (!axe.commons.forms.isNativeSelect(node)) {
		return '';
	}
	return (
		Array.from(node.options)
			.filter(option => option.selected)
			.map(option => option.text)
			.join(' ') || ''
	);
}

/**
 * Calculate value of a an element with role=textbox
 *
 * @param {VirtualNode} element The VirtualNode instance whose value we want
 * @return {string} The calculated value
 */
function ariaTextboxValue(virtualNode) {
	const { actualNode } = virtualNode;
	if (!axe.commons.forms.isAriaTextbox(actualNode)) {
		return '';
	}
	if (!dom.isHiddenWithCSS(actualNode)) {
		return text.visibleVirtual(virtualNode, true);
	} else {
		return actualNode.textContent;
	}
}

/**
 * Calculate value of an element with role=combobox or role=listbox
 *
 * @param {VirtualNode} element The VirtualNode instance whose value we want
 * @param {Object} context The VirtualNode instance whose value we want
 * @property {Element} startNode First node in accessible name computation
 * @property {String[]} unsupported List of roles where value computation is unsupported
 * @property {Bool} debug Enable logging for formControlValue
 * @return {string} The calculated value
 */
function ariaListboxValue(virtualNode, context) {
	const { actualNode } = virtualNode;
	if (!axe.commons.forms.isAriaListbox(actualNode)) {
		return '';
	}

	const selected = aria
		.getOwnedVirtual(virtualNode)
		.filter(
			owned =>
				aria.getRole(owned) === 'option' &&
				owned.actualNode.getAttribute('aria-selected') === 'true'
		);

	if (selected.length === 0) {
		return '';
	}
	// Note: Even with aria-multiselectable, only the first value will be used
	// in the accessible name. This isn't spec'ed out, but seems to be how all
	// browser behave.
	return axe.commons.text.accessibleTextVirtual(selected[0], context);
}

/**
 * Calculate value of an element with role=combobox or role=listbox
 *
 * @param {VirtualNode} element The VirtualNode instance whose value we want
 * @param {Object} context The VirtualNode instance whose value we want
 * @property {Element} startNode First node in accessible name computation
 * @property {String[]} unsupported List of roles where value computation is unsupported
 * @property {Bool} debug Enable logging for formControlValue
 * @return {string} The calculated value
 */
function ariaComboboxValue(virtualNode, context) {
	const { actualNode } = virtualNode;
	let listbox;

	// For combobox, find the first owned listbox:
	if (!axe.commons.forms.isAriaCombobox(actualNode)) {
		return '';
	}
	listbox = aria
		.getOwnedVirtual(virtualNode)
		.filter(elm => aria.getRole(elm) === 'listbox')[0];

	return listbox
		? text.formControlValueMethods.ariaListboxValue(listbox, context)
		: '';
}

/**
 * Calculate value of an element with range-type role
 *
 * @param {VirtualNode|Node} element The VirtualNode instance whose value we want
 * @return {string} The calculated value
 */
function ariaRangeValue(node) {
	node = node.actualNode || node;
	if (
		!axe.commons.forms.isAriaRange(node) ||
		!node.hasAttribute('aria-valuenow')
	) {
		return '';
	}
	// Validate the number, if not, return 0.
	// Chrome 70 typecasts this, Firefox 62 does not
	const valueNow = +node.getAttribute('aria-valuenow');
	return !isNaN(valueNow) ? String(valueNow) : '0';
}
