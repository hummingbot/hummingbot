var children = virtualNode.children;
if (!children || !children.length) {
	return false;
}

var hasDt = false,
	hasDd = false,
	nodeName;
for (var i = 0; i < children.length; i++) {
	nodeName = children[i].actualNode.nodeName.toUpperCase();
	if (nodeName === 'DT') {
		hasDt = true;
	}
	if (hasDt && nodeName === 'DD') {
		return false;
	}
	if (nodeName === 'DD') {
		hasDd = true;
	}
}

return hasDt || hasDd;
