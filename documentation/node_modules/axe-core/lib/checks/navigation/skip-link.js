const target = axe.commons.dom.getElementByReference(node, 'href');
if (target) {
	return axe.commons.dom.isVisible(target, true) || undefined;
}
return false;
