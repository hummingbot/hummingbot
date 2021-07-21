/* global aria, matches */
/**
 * @description validate if a given role is an allowed ARIA role for the supplied node
 * @method isAriaRoleAllowedOnElement
 * @param {HTMLElement} node the node to verify
 * @param {String} role aria role to check
 * @return {Boolean} retruns true/false
 */
aria.isAriaRoleAllowedOnElement = function isAriaRoleAllowedOnElement(
	node,
	role
) {
	const nodeName = node.nodeName.toUpperCase();
	const lookupTable = axe.commons.aria.lookupTable;

	// if given node can have no role - return false
	if (matches(node, lookupTable.elementsAllowedNoRole)) {
		return false;
	}
	// if given node allows any role - return true
	if (matches(node, lookupTable.elementsAllowedAnyRole)) {
		return true;
	}

	// get role value (if exists) from lookupTable.role
	const roleValue = lookupTable.role[role];

	// if given role does not exist in lookupTable - return false
	if (!roleValue || !roleValue.allowedElements) {
		return false;
	}

	// validate attributes and conditions (if any) from allowedElement to given node
	let out = matches(node, roleValue.allowedElements);

	// if given node type has complex condition to evaluate a given aria-role, execute the same
	if (Object.keys(lookupTable.evaluateRoleForElement).includes(nodeName)) {
		return lookupTable.evaluateRoleForElement[nodeName]({ node, role, out });
	}
	return out;
};
