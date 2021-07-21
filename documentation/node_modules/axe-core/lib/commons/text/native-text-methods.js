/* global text */

const defaultButtonValues = {
	submit: 'Submit',
	image: 'Submit',
	reset: 'Reset',
	button: '' // No default for "button"
};

text.nativeTextMethods = {
	/**
	 * Return the value of a DOM node
	 * @param {VirtualNode} element
	 * @return {String} value text
	 */
	valueText: ({ actualNode }) => actualNode.value || '',

	/**
	 * Return default value of a button
	 * @param {VirtualNode} element
	 * @return {String} default button text
	 */
	buttonDefaultText: ({ actualNode }) =>
		defaultButtonValues[actualNode.type] || '',

	/**
	 * Return caption text of an HTML table element
	 * @param {VirtualNode} element
	 * @param {Object} context
	 * @return {String} caption text
	 */
	tableCaptionText: descendantText.bind(null, 'caption'),

	/**
	 * Return figcaption text of an HTML figure element
	 * @param {VirtualNode} element
	 * @param {Object} context
	 * @return {String} figcaption text
	 */
	figureText: descendantText.bind(null, 'figcaption'),

	/**
	 * Return legend text of an HTML fieldset element
	 * @param {VirtualNode} element
	 * @param {Object} context
	 * @return {String} legend text
	 */
	fieldsetLegendText: descendantText.bind(null, 'legend'),

	/**
	 * Return the alt text
	 * @param {VirtualNode} element
	 * @return {String} alt text
	 */
	altText: attrText.bind(null, 'alt'),

	/**
	 * Return summary text for an HTML table element
	 * @param {VirtualNode} element
	 * @return {String} summary text
	 */
	tableSummaryText: attrText.bind(null, 'summary'),

	/**
	 * Return the title text
	 * @param {VirtualNode} element
	 * @return {String} title text
	 */
	titleText: function titleText(virtualNode, context) {
		return text.titleText(virtualNode, context);
	},

	/**
	 * Return accessible text of the subtree
	 * @param {VirtualNode} element
	 * @param {Object} context
	 * @return {String} Subtree text
	 */
	subtreeText: function subtreeText(virtualNode, context) {
		return text.subtreeText(virtualNode, context);
	},

	/**
	 * Return accessible text for an implicit and/or explicit HTML label element
	 * @param {VirtualNode} element
	 * @param {Object} context
	 * @return {String} Label text
	 */
	labelText: function labelText(virtualNode, context) {
		return text.labelText(virtualNode, context);
	},

	/**
	 * Return a single space
	 * @return {String} Returns ` `
	 */
	singleSpace: function singleSpace() {
		return ' ';
	}
};

function attrText(attr, { actualNode }) {
	return actualNode.getAttribute(attr) || '';
}

/**
 * Get the accessible text of first matching node
 * IMPORTANT: This method does not look at the composed tree
 * @private
 */
function descendantText(nodeName, { actualNode }, context) {
	nodeName = nodeName.toLowerCase();
	// Prevent accidently getting the nested element, like:
	// fieldset > fielset > legend (1st fieldset has no legend)
	const nodeNames = [nodeName, actualNode.nodeName.toLowerCase()].join(',');
	const candidate = actualNode.querySelector(nodeNames);

	if (!candidate || candidate.nodeName.toLowerCase() !== nodeName) {
		return '';
	}
	return text.accessibleText(candidate, context);
}
