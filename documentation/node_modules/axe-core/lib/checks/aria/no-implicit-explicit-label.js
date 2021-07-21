const { aria, text } = axe.commons;

const role = aria.getRole(node, { noImplicit: true });
this.data(role);

const labelText = text.sanitize(text.labelText(virtualNode)).toLowerCase();
const accText = text.sanitize(text.accessibleText(node)).toLowerCase();

if (!accText && !labelText) {
	return false;
}

if (!accText && labelText) {
	return undefined;
}

if (!accText.includes(labelText)) {
	return undefined;
}

return false;
