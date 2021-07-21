const elementsThatCanBeDisabled = [
	'BUTTON',
	'FIELDSET',
	'INPUT',
	'SELECT',
	'TEXTAREA'
];

const tabbableElements = virtualNode.tabbableElements;

if (!tabbableElements || !tabbableElements.length) {
	return true;
}

const relatedNodes = tabbableElements.reduce((out, { actualNode: el }) => {
	const nodeName = el.nodeName.toUpperCase();
	// populate nodes that can be disabled
	if (elementsThatCanBeDisabled.includes(nodeName)) {
		out.push(el);
	}
	return out;
}, []);

this.relatedNodes(relatedNodes);

if (relatedNodes.length && axe.commons.dom.isModalOpen()) {
	return true;
}

return relatedNodes.length === 0;
