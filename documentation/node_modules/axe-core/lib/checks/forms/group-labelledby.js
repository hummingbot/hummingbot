const { dom, text } = axe.commons;

const type = axe.utils.escapeSelector(node.type);
const name = axe.utils.escapeSelector(node.name);
const doc = dom.getRootNode(node);
const data = {
	name: node.name,
	type: node.type
};

const matchingNodes = Array.from(
	doc.querySelectorAll(`input[type="${type}"][name="${name}"]`)
);
// There is only one node with this name & type, so there's no need for a group
if (matchingNodes.length <= 1) {
	this.data(data);
	return true;
}

let sharedLabels = dom.idrefs(node, 'aria-labelledby').filter(label => !!label); // Filter for "null" labels
let uniqueLabels = sharedLabels.slice();

// Figure out which labels are unique, which are shared by all items, or neither
matchingNodes.forEach(groupItem => {
	if (groupItem === node) {
		return;
	}
	// Find new labels associated with current groupItem
	const labels = dom
		.idrefs(groupItem, 'aria-labelledby')
		.filter(newLabel => newLabel);

	sharedLabels = sharedLabels.filter(sharedLabel =>
		labels.includes(sharedLabel)
	);
	uniqueLabels = uniqueLabels.filter(
		uniqueLabel => !labels.includes(uniqueLabel)
	);
});

const accessibleTextOptions = {
	// Prevent following further aria-labelledby refs:
	inLabelledByContext: true
};

// filter items with no accessible name, do this last for performance reasons
uniqueLabels = uniqueLabels.filter(labelNode =>
	text.accessibleText(labelNode, accessibleTextOptions)
);
sharedLabels = sharedLabels.filter(labelNode =>
	text.accessibleText(labelNode, accessibleTextOptions)
);

if (uniqueLabels.length > 0 && sharedLabels.length > 0) {
	this.data(data);
	return true;
}

if (uniqueLabels.length > 0 && sharedLabels.length === 0) {
	data.messageKey = 'no-shared-label';
} else if (uniqueLabels.length === 0 && sharedLabels.length > 0) {
	data.messageKey = 'no-unique-label';
}

this.data(data);
return false;
