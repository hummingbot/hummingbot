/* global aria, dom */

/**
 * Validate the value of an ARIA attribute
 * @method validateAttrValue
 * @memberof axe.commons.aria
 * @instance
 * @param  {HTMLElement} node The element to check
 * @param  {String} attr The name of the attribute
 * @return {Boolean}
 */
aria.validateAttrValue = function validateAttrValue(node, attr) {
	'use strict';
	var matches,
		list,
		value = node.getAttribute(attr),
		attrInfo = aria.lookupTable.attributes[attr];

	var doc = dom.getRootNode(node);

	if (!attrInfo) {
		return true;
	}
	if (attrInfo.allowEmpty && (!value || value.trim() === '')) {
		return true;
	}

	switch (attrInfo.type) {
		case 'boolean':
		case 'nmtoken':
			return (
				typeof value === 'string' &&
				attrInfo.values.includes(value.toLowerCase())
			);

		case 'nmtokens':
			list = axe.utils.tokenList(value);
			// Check if any value isn't in the list of values
			return list.reduce(function(result, token) {
				return result && attrInfo.values.includes(token);
				// Initial state, fail if the list is empty
			}, list.length !== 0);

		case 'idref':
			return !!(value && doc.getElementById(value));

		case 'idrefs':
			list = axe.utils.tokenList(value);
			return list.some(token => doc.getElementById(token));

		case 'string':
			// Not allowed empty except with allowEmpty: true
			return value.trim() !== '';

		case 'decimal':
			matches = value.match(/^[-+]?([0-9]*)\.?([0-9]*)$/);
			return !!(matches && (matches[1] || matches[2]));

		case 'int':
			return /^[-+]?[0-9]+$/.test(value);
	}
};
