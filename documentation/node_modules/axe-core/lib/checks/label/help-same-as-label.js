var labelText = axe.commons.text.labelVirtual(virtualNode),
	check = node.getAttribute('title');

if (!labelText) {
	return false;
}

if (!check) {
	check = '';

	if (node.getAttribute('aria-describedby')) {
		var ref = axe.commons.dom.idrefs(node, 'aria-describedby');
		check = ref
			.map(function(thing) {
				return thing ? axe.commons.text.accessibleText(thing) : '';
			})
			.join('');
	}
}

return (
	axe.commons.text.sanitize(check) === axe.commons.text.sanitize(labelText)
);
