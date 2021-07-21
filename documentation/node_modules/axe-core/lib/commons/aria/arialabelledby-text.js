/* global aria, dom, text */

/**
 * Get the accessible name based on aria-labelledby
 *
 * @param {VirtualNode} element
 * @param {Object} context
 * @property {Bool} inLabelledByContext Whether or not the lookup is part of aria-labelledby reference
 * @property {Bool} inControlContext Whether or not the lookup is part of a native label reference
 * @property {Element} startNode First node in accessible name computation
 * @property {Bool} debug Enable logging for formControlValue
 * @return {string} Cancatinated text value for referenced elements
 */
aria.arialabelledbyText = function arialabelledbyText(node, context = {}) {
	node = node.actualNode || node;
	/**
	 * Note: The there are significant difference in how many "leads" browsers follow.
	 * - Firefox stops after the first IDREF, so it
	 * 		doesn't follow aria-labelledby after a for:>ID ref.
	 * - Chrome seems to just keep iterating no matter how many levels deep.
	 * - AccName-AAM 1.1 suggests going one level deep, but to treat
	 * 		each ref type separately.
	 *
	 * Axe-core's implementation behaves most closely like Firefox as it seems
	 *  to be the common denominator. Main difference is that Firefox
	 *  includes the value of form controls in addition to aria-label(s),
	 *  something no other browser seems to do. Axe doesn't do that.
	 */
	if (
		node.nodeType !== 1 ||
		context.inLabelledByContext ||
		context.inControlContext
	) {
		return '';
	}

	const refs = dom.idrefs(node, 'aria-labelledby').filter(elm => elm);
	return refs.reduce((accessibleName, elm) => {
		const accessibleNameAdd = text.accessibleText(elm, {
			// Prevent the infinite reference loop:
			inLabelledByContext: true,
			startNode: context.startNode || node,
			...context
		});

		if (!accessibleName) {
			return accessibleNameAdd;
		} else {
			return `${accessibleName} ${accessibleNameAdd}`;
		}
	}, '');
};
