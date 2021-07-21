const abstractRoles = axe.utils
	.tokenList(virtualNode.attr('role'))
	.filter(role => axe.commons.aria.getRoleType(role) === 'abstract');

if (abstractRoles.length > 0) {
	this.data(abstractRoles);
	return true;
}

return false;
