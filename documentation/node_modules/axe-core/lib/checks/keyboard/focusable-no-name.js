var tabIndex = node.getAttribute('tabindex'),
	inFocusOrder = axe.commons.dom.isFocusable(node) && tabIndex > -1;
if (!inFocusOrder) {
	return false;
}
return !axe.commons.text.accessibleTextVirtual(virtualNode);
