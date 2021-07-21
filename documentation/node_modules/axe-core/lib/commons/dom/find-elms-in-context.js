/* global axe, dom */

/**
 * Find elements referenced from a given context
 * @method findElmsInContext
 * @memberof axe.commons.dom
 * @instance
 * @param {Object} element
 * @param {String} element.context Element in the same context
 * @param {String} element.value Attribute value to search for
 * @param {String} element.attr Attribute name to search for
 * @param {String} element.elm NodeName to search for (optional)
 * @return {Array<Node>}
 */
dom.findElmsInContext = function({ context, value, attr, elm = '' }) {
	let root;
	const escapedValue = axe.utils.escapeSelector(value);

	if (context.nodeType === 9 || context.nodeType === 11) {
		// It's already root
		root = context;
	} else {
		root = dom.getRootNode(context);
	}
	return Array.from(
		root.querySelectorAll(elm + '[' + attr + '=' + escapedValue + ']')
	);
};
