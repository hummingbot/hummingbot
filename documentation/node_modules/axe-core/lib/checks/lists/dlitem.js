let parent = axe.commons.dom.getComposedParent(node);
let parentTagName = parent.nodeName.toUpperCase();
let parentRole = axe.commons.aria.getRole(parent, { noImplicit: true });

if (
	parentTagName === 'DIV' &&
	['presentation', 'none', null].includes(parentRole)
) {
	parent = axe.commons.dom.getComposedParent(parent);
	parentTagName = parent.nodeName.toUpperCase();
	parentRole = axe.commons.aria.getRole(parent, { noImplicit: true });
}

// Unlike with UL|OL+LI, DT|DD must be in a DL
if (parentTagName !== 'DL') {
	return false;
}

if (!parentRole || parentRole === 'list') {
	return true;
}

return false;
