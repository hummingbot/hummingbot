const nodeName = node.nodeName.toUpperCase();
const lookupTable = axe.commons.aria.lookupTable;
const role = axe.commons.aria.getRole(node);

const unsupportedAttrs = Array.from(axe.utils.getNodeAttributes(node))
	.filter(({ name }) => {
		const attribute = lookupTable.attributes[name];

		if (!axe.commons.aria.validateAttr(name)) {
			return false;
		}

		const { unsupported } = attribute;

		if (typeof unsupported !== 'object') {
			return !!unsupported;
		}

		// validate attributes and conditions (if any) from allowedElement to given node
		const isException = axe.commons.matches(node, unsupported.exceptions);

		if (!Object.keys(lookupTable.evaluateRoleForElement).includes(nodeName)) {
			return !isException;
		}

		// evaluate a given aria-role, execute the same
		return !lookupTable.evaluateRoleForElement[nodeName]({
			node,
			role,
			out: isException
		});
	})
	.map(candidate => candidate.name.toString());

if (unsupportedAttrs.length) {
	this.data(unsupportedAttrs);
	return true;
}
return false;
