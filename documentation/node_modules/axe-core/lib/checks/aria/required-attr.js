options = options || {};

const missing = [];
const {
	isNativeTextbox,
	isNativeSelect,
	isAriaTextbox,
	isAriaListbox,
	isAriaCombobox,
	isAriaRange
} = axe.commons.forms;

// aria-valuenow should fail if element does not have a value property
// @see https://github.com/dequelabs/axe-core/issues/1501
const preChecks = {
	'aria-valuenow': function() {
		return !(
			isNativeTextbox(node) ||
			isNativeSelect(node) ||
			isAriaTextbox(node) ||
			isAriaListbox(node) ||
			isAriaCombobox(node) ||
			(isAriaRange(node) && node.hasAttribute('aria-valuenow'))
		);
	}
};

if (node.hasAttributes()) {
	const role = node.getAttribute('role');
	let required = axe.commons.aria.requiredAttr(role);

	if (Array.isArray(options[role])) {
		required = axe.utils.uniqueArray(options[role], required);
	}
	if (role && required) {
		for (let i = 0, l = required.length; i < l; i++) {
			const attr = required[i];
			if (
				!node.getAttribute(attr) &&
				(preChecks[attr] ? preChecks[attr]() : true)
			) {
				missing.push(attr);
			}
		}
	}
}

if (missing.length) {
	this.data(missing);
	return false;
}

return true;
