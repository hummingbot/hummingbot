/* global dom, text */

/**
 * Return accessible text for an implicit and/or explicit HTML label element
 * @param {VirtualNode} element
 * @param {Object} context
 * @property {Bool} inControlContext
 * @property {Bool} inLabelledByContext
 * @return {String} Label text
 */
text.labelText = function labelText(virtualNode, context = {}) {
	const { alreadyProcessed } = text.accessibleTextVirtual;
	if (
		context.inControlContext ||
		context.inLabelledByContext ||
		alreadyProcessed(virtualNode, context)
	) {
		return '';
	}
	if (!context.startNode) {
		context.startNode = virtualNode;
	}

	const labelContext = { inControlContext: true, ...context };
	const explicitLabels = getExplicitLabels(virtualNode);
	const implicitLabel = dom.findUpVirtual(virtualNode, 'label');

	let labels;
	if (implicitLabel) {
		labels = [...explicitLabels, implicitLabel];
		labels.sort(axe.utils.nodeSorter);
	} else {
		labels = explicitLabels;
	}

	return labels
		.map(label => text.accessibleText(label, labelContext))
		.filter(text => text !== '')
		.join(' ');
};

/**
 * Find a non-ARIA label for an element
 * @private
 * @param {VirtualNode} element The VirtualNode instance whose label we are seeking
 * @return {HTMLElement} The label element, or null if none is found
 */
function getExplicitLabels({ actualNode }) {
	if (!actualNode.id) {
		return [];
	}
	return dom.findElmsInContext({
		elm: 'label',
		attr: 'for',
		value: actualNode.id,
		context: actualNode
	});
}
