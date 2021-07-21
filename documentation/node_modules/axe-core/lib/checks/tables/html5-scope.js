if (!axe.commons.dom.isHTML5(document)) {
	return true;
}

return node.nodeName.toUpperCase() === 'TH';
