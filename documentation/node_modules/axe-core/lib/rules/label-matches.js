if (
	node.nodeName.toLowerCase() !== 'input' ||
	node.hasAttribute('type') === false
) {
	return true;
}

var type = node.getAttribute('type').toLowerCase();
return (
	['hidden', 'image', 'button', 'submit', 'reset'].includes(type) === false
);
