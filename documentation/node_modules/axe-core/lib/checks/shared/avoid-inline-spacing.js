const inlineSpacingCssProperties = [
	'line-height',
	'letter-spacing',
	'word-spacing'
];

const overriddenProperties = inlineSpacingCssProperties.filter(property => {
	if (node.style.getPropertyPriority(property) === `important`) {
		return property;
	}
});

if (overriddenProperties.length > 0) {
	this.data(overriddenProperties);
	return false;
}

return true;
