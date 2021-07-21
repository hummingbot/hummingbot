options = options || {};

var invalid = [];

var attr,
	attrName,
	allowed,
	role = node.getAttribute('role'),
	attrs = axe.utils.getNodeAttributes(node);

if (!role) {
	role = axe.commons.aria.implicitRole(node);
}

allowed = axe.commons.aria.allowedAttr(role);

if (Array.isArray(options[role])) {
	allowed = axe.utils.uniqueArray(options[role].concat(allowed));
}

if (role && allowed) {
	for (var i = 0, l = attrs.length; i < l; i++) {
		attr = attrs[i];
		attrName = attr.name;
		if (
			axe.commons.aria.validateAttr(attrName) &&
			!allowed.includes(attrName)
		) {
			invalid.push(attrName + '="' + attr.nodeValue + '"');
		}
	}
}

if (invalid.length) {
	this.data(invalid);
	return false;
}

return true;
