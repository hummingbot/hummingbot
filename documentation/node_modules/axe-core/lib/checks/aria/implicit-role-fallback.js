var role = node.getAttribute('role');
if (role === null || !axe.commons.aria.isValidRole(role)) {
	return true;
}
var roleType = axe.commons.aria.getRoleType(role);
return axe.commons.aria.implicitRole(node) === roleType;
