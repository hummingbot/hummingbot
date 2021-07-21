let nodeName = node.nodeName.toUpperCase();
let role = node.getAttribute('role');
let label;

if (nodeName === 'BUTTON' || (role === 'button' && nodeName !== 'INPUT')) {
	label = axe.commons.text.accessibleTextVirtual(virtualNode);
	this.data(label);

	return !!label;
} else {
	return false;
}
