const tabbableElements = virtualNode.tabbableElements.map(
	({ actualNode }) => actualNode
);

if (!tabbableElements || !tabbableElements.length) {
	return true;
}

if (axe.commons.dom.isModalOpen()) {
	this.relatedNodes(tabbableElements);
	return undefined;
}

return true;
