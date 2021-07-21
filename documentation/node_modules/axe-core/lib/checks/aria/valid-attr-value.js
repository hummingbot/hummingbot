options = Array.isArray(options) ? options : [];

let needsReview = '';
let messageKey = '';
const invalid = [];
const aria = /^aria-/;
const attrs = axe.utils.getNodeAttributes(node);

const skipAttrs = ['aria-errormessage'];

const preChecks = {
	// aria-controls should only check if element exists if the element
	// doesn't have aria-expanded=false or aria-selected=false (tabs)
	// @see https://github.com/dequelabs/axe-core/issues/1463
	'aria-controls': () => {
		return (
			node.getAttribute('aria-expanded') !== 'false' &&
			node.getAttribute('aria-selected') !== 'false'
		);
	},
	// aria-current should mark as needs review if any value is used that is
	// not one of the valid values (since any value is treated as "true")
	'aria-current': () => {
		if (!axe.commons.aria.validateAttrValue(node, 'aria-current')) {
			needsReview = `aria-current="${node.getAttribute('aria-current')}"`;
			messageKey = 'ariaCurrent';
		}

		return;
	},
	// aria-owns should only check if element exists if the element
	// doesn't have aria-expanded=false (combobox)
	// @see https://github.com/dequelabs/axe-core/issues/1524
	'aria-owns': () => {
		return node.getAttribute('aria-expanded') !== 'false';
	},
	// aria-describedby should not mark missing element as violation but
	// instead as needs review
	// @see https://github.com/dequelabs/axe-core/issues/1151
	'aria-describedby': () => {
		if (!axe.commons.aria.validateAttrValue(node, 'aria-describedby')) {
			needsReview = `aria-describedby="${node.getAttribute(
				'aria-describedby'
			)}"`;
			messageKey = 'noId';
		}

		return;
	}
};

for (let i = 0, l = attrs.length; i < l; i++) {
	const attr = attrs[i];
	const attrName = attr.name;
	// skip any attributes handled elsewhere
	if (
		!skipAttrs.includes(attrName) &&
		options.indexOf(attrName) === -1 &&
		aria.test(attrName) &&
		(preChecks[attrName] ? preChecks[attrName]() : true) &&
		!axe.commons.aria.validateAttrValue(node, attrName)
	) {
		invalid.push(`${attrName}="${attr.nodeValue}"`);
	}
}

if (needsReview) {
	this.data({
		messageKey,
		needsReview
	});
	return undefined;
}

if (invalid.length) {
	this.data(invalid);
	return false;
}

return true;
