const { tokenList } = axe.utils;
const { aria } = axe.commons;

const allRoles = tokenList(virtualNode.attr('role'));
const allInvalid = allRoles.every(
	role => !aria.isValidRole(role, { allowAbstract: true })
);

/**
 * Only fail when all the roles are invalid
 */
if (allInvalid) {
	this.data(allRoles);
	return true;
}

return false;
