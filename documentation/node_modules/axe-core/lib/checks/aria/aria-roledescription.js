options = options || {};

const role = axe.commons.aria.getRole(node);
const supportedRoles = options.supportedRoles || [];

if (supportedRoles.includes(role)) {
	return true;
}

if (role && role !== 'presentation' && role !== 'none') {
	return undefined;
}

return false;
