if (node.getAttribute('id')) {
	const root = axe.commons.dom.getRootNode(node);
	const id = axe.utils.escapeSelector(node.getAttribute('id'));
	const label = root.querySelector(`label[for="${id}"]`);

	if (label) {
		// defer to hidden-explicit-label check for better messaging
		if (!axe.commons.dom.isVisible(label)) {
			return true;
		} else {
			return !!axe.commons.text.accessibleText(label);
		}
	}
}
return false;
