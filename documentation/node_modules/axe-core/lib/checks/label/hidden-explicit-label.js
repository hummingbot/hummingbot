if (node.getAttribute('id')) {
	const root = axe.commons.dom.getRootNode(node);
	const id = axe.utils.escapeSelector(node.getAttribute('id'));
	const label = root.querySelector(`label[for="${id}"]`);

	if (label && !axe.commons.dom.isVisible(label, true)) {
		const name = axe.commons.text.accessibleTextVirtual(virtualNode).trim();
		const isNameEmpty = name === '';
		return isNameEmpty;
	}
}
return false;
