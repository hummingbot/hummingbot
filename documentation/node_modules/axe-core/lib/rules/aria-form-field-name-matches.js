/**
 * Note:
 * This rule filters elements with 'role=*' attribute via 'selector'
 * see relevant rule spec for details of 'role(s)' being filtered.
 */
const { aria } = axe.commons;

const nodeName = node.nodeName.toUpperCase();
const role = aria.getRole(node, { noImplicit: true });

/**
 * Ignore elements from rule -> 'area-alt'
 */
if (nodeName === 'AREA' && !!node.getAttribute('href')) {
	return false;
}

/**
 * Ignore elements from rule -> 'label'
 */
if (['INPUT', 'SELECT', 'TEXTAREA'].includes(nodeName)) {
	return false;
}

/**
 * Ignore elements from rule -> 'image-alt'
 */
if (nodeName === 'IMG' || (role === 'img' && nodeName !== 'SVG')) {
	return false;
}

/**
 * Ignore elements from rule -> 'button-name'
 */
if (nodeName === 'BUTTON' || role === 'button') {
	return false;
}

/**
 * Ignore combobox elements if they have a child input
 * (ARIA 1.1 pattern)
 */
if (
	role === 'combobox' &&
	axe.utils.querySelectorAll(virtualNode, 'input:not([type="hidden"])').length
) {
	return false;
}

return true;
