// Check for 'default' names, which are given to reset and submit buttons
let nodeName = node.nodeName.toUpperCase();
let type = (node.getAttribute('type') || '').toLowerCase();
let label = node.getAttribute('value');

if (label) {
	this.data({
		messageKey: 'has-label'
	});
}

if (nodeName === 'INPUT' && ['submit', 'reset'].includes(type)) {
	return label === null;
}
return false;
