var role = node.getAttribute('role');
if (role === null) {
	return false;
}
var roleType = axe.commons.aria.getRoleType(role);
return roleType === 'widget' || roleType === 'composite';
