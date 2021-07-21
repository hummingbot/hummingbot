const { aria, text } = axe.commons;

const hasAccName = !!text.accessibleTextVirtual(virtualNode);
if (!hasAccName) {
	return false;
}

const role = aria.getRole(node);
if (role && role !== 'link') {
	return false;
}

return true;
