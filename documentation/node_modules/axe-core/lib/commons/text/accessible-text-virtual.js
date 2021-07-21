/* global text, dom, aria, axe */

/**
 * Finds virtual node and calls accessibleTextVirtual()
 * IMPORTANT: This method requires the composed tree at axe._tree
 *
 * @param {HTMLElement} element The HTMLElement
 * @param {Object} context
 * @property {Bool} inControlContext
 * @property {Bool} inLabelledByContext
 * @return {string}
 */
text.accessibleText = function accessibleText(element, context) {
	const virtualNode = axe.utils.getNodeFromTree(element); // throws an exception on purpose if axe._tree not correct
	return text.accessibleTextVirtual(virtualNode, context);
};

/**
 * Finds virtual node and calls accessibleTextVirtual()
 * IMPORTANT: This method requires the composed tree at axe._tree
 *
 * @param {HTMLElement} element The HTMLElement
 * @param {Object} context
 * @property {Bool} inControlContext
 * @property {Bool} inLabelledByContext
 * @return {string}
 */
text.accessibleTextVirtual = function accessibleTextVirtual(
	virtualNode,
	context = {}
) {
	const { actualNode } = virtualNode;
	context = prepareContext(virtualNode, context);

	// Step 2A, check visibility
	if (shouldIgnoreHidden(virtualNode, context)) {
		return '';
	}

	const computationSteps = [
		aria.arialabelledbyText, // Step 2B.1
		aria.arialabelText, // Step 2C
		text.nativeTextAlternative, // Step 2D
		text.formControlValue, // Step 2E
		text.subtreeText, // Step 2F + Step 2H
		textNodeContent, // Step 2G (order with 2H does not matter)
		text.titleText // Step 2I
	];

	// Find the first step that returns a non-empty string
	let accName = computationSteps.reduce((accName, step) => {
		if (context.startNode === virtualNode) {
			accName = text.sanitize(accName);
		}

		if (accName !== '') {
			// yes, whitespace only a11y names halt the algorithm
			return accName;
		}
		return step(virtualNode, context);
	}, '');

	if (context.debug) {
		axe.log(accName || '{empty-value}', actualNode, context);
	}
	return accName;
};

/**
 * Return the textContent of a node
 * @param {VirtualNode} element
 * @return {String} textContent value
 */
function textNodeContent({ actualNode }) {
	if (actualNode.nodeType !== 3) {
		return '';
	}
	return actualNode.textContent;
}

/**
 * Check if the
 * @param {VirtualNode} element
 * @param {Object} context
 * @property {VirtualNode[]} processed
 * @return {Boolean}
 */
function shouldIgnoreHidden({ actualNode }, context) {
	if (
		// If the parent isn't ignored, the text node should not be either
		actualNode.nodeType !== 1 ||
		// If the target of aria-labelledby is hidden, ignore all descendents
		context.includeHidden
	) {
		return false;
	}

	return !dom.isVisible(actualNode, true);
}

/**
 * Apply defaults to the context
 * @param {VirtualNode} element
 * @param {Object} context
 * @return {Object} context object with defaults applied
 */
function prepareContext(virtualNode, context) {
	const { actualNode } = virtualNode;
	if (!context.startNode) {
		context = { startNode: virtualNode, ...context };
	}
	/**
	 * When `aria-labelledby` directly references a `hidden` element
	 * the element needs to be included in the accessible name.
	 *
	 * When a descendent of the `aria-labelledby` reference is `hidden`
	 * the element should not be included in the accessible name.
	 *
	 * This is done by setting `includeHidden` for the `aria-labelledby` reference.
	 */
	if (
		actualNode.nodeType === 1 &&
		context.inLabelledByContext &&
		context.includeHidden === undefined
	) {
		context = {
			includeHidden: !dom.isVisible(actualNode, true),
			...context
		};
	}
	return context;
}

/**
 * Check if the node is processed with this context before
 * @param {VirtualNode} element
 * @param {Object} context
 * @property {VirtualNode[]} processed
 * @return {Boolean}
 */
text.accessibleTextVirtual.alreadyProcessed = function alreadyProcessed(
	virtualnode,
	context
) {
	context.processed = context.processed || [];
	if (context.processed.includes(virtualnode)) {
		return true;
	}

	context.processed.push(virtualnode);
	return false;
};
