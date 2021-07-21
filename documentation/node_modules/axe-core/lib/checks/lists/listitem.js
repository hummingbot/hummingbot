const parent = axe.commons.dom.getComposedParent(node);
if (!parent) {
	// Can only happen with detached DOM nodes and roots:
	return undefined;
}

const parentTagName = parent.nodeName.toUpperCase();
const parentRole = (parent.getAttribute('role') || '').toLowerCase();

if (['presentation', 'none', 'list'].includes(parentRole)) {
	return true;
}

if (parentRole && axe.commons.aria.isValidRole(parentRole)) {
	this.data({
		messageKey: 'roleNotValid'
	});
	return false;
}

return ['UL', 'OL'].includes(parentTagName);
