const { aria, text, dom } = axe.commons;

if (['none', 'presentation'].includes(aria.getRole(node))) {
	return false;
}

const parent = dom.findUpVirtual(
	virtualNode,
	'button, [role="button"], a[href], p, li, td, th'
);

if (!parent) {
	return false;
}

const parentVNode = axe.utils.getNodeFromTree(parent);
const visibleText = text.visibleVirtual(parentVNode, true).toLowerCase();
if (visibleText === '') {
	return false;
}

return visibleText === text.accessibleTextVirtual(virtualNode).toLowerCase();
