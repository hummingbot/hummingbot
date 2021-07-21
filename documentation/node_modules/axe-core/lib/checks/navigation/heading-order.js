var ariaHeadingLevel = node.getAttribute('aria-level');

if (ariaHeadingLevel !== null) {
	this.data(parseInt(ariaHeadingLevel, 10));
	return true;
}

var headingLevel = node.nodeName.toUpperCase().match(/H(\d)/);

if (headingLevel) {
	this.data(parseInt(headingLevel[1], 10));
	return true;
}

return true;
