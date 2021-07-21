var failureCode,
	self = this;

function getUnrelatedElements(parent, name) {
	return axe.utils.toArray(
		parent.querySelectorAll(
			'select,textarea,button,input:not([name="' +
				name +
				'"]):not([type="hidden"])'
		)
	);
}

function checkFieldset(group, name) {
	var firstNode = group.firstElementChild;
	if (!firstNode || firstNode.nodeName.toUpperCase() !== 'LEGEND') {
		self.relatedNodes([group]);
		failureCode = 'no-legend';
		return false;
	}
	if (!axe.commons.text.accessibleText(firstNode)) {
		self.relatedNodes([firstNode]);
		failureCode = 'empty-legend';
		return false;
	}
	var otherElements = getUnrelatedElements(group, name);
	if (otherElements.length) {
		self.relatedNodes(otherElements);
		failureCode = 'mixed-inputs';
		return false;
	}
	return true;
}

function checkARIAGroup(group, name) {
	var hasLabelledByText = axe.commons.dom
		.idrefs(group, 'aria-labelledby')
		.some(function(element) {
			return element && axe.commons.text.accessibleText(element);
		});
	var ariaLabel = group.getAttribute('aria-label');
	if (
		!hasLabelledByText &&
		!(ariaLabel && axe.commons.text.sanitize(ariaLabel))
	) {
		self.relatedNodes(group);
		failureCode = 'no-group-label';
		return false;
	}

	var otherElements = getUnrelatedElements(group, name);
	if (otherElements.length) {
		self.relatedNodes(otherElements);
		failureCode = 'group-mixed-inputs';
		return false;
	}
	return true;
}

function spliceCurrentNode(nodes, current) {
	return axe.utils.toArray(nodes).filter(function(candidate) {
		return candidate !== current;
	});
}

function runCheck(virtualNode) {
	const name = axe.utils.escapeSelector(virtualNode.actualNode.name);
	const root = axe.commons.dom.getRootNode(virtualNode.actualNode);
	const matchingNodes = root.querySelectorAll(
		'input[type="' +
			axe.utils.escapeSelector(virtualNode.actualNode.type) +
			'"][name="' +
			name +
			'"]'
	);

	if (matchingNodes.length < 2) {
		return true;
	}
	const fieldset = axe.commons.dom.findUpVirtual(virtualNode, 'fieldset');
	const group = axe.commons.dom.findUpVirtual(
		virtualNode,
		'[role="group"]' +
			(virtualNode.actualNode.type === 'radio' ? ',[role="radiogroup"]' : '')
	);

	if (!group && !fieldset) {
		failureCode = 'no-group';
		self.relatedNodes(spliceCurrentNode(matchingNodes, virtualNode.actualNode));
		return false;
	} else if (fieldset) {
		return checkFieldset(fieldset, name);
	} else {
		return checkARIAGroup(group, name);
	}
}

var data = {
	name: node.getAttribute('name'),
	type: node.getAttribute('type')
};

var result = runCheck(virtualNode);
if (!result) {
	data.messageKey = failureCode;
}
this.data(data);

return result;
