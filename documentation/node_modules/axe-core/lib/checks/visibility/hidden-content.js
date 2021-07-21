const whitelist = ['SCRIPT', 'HEAD', 'TITLE', 'NOSCRIPT', 'STYLE', 'TEMPLATE'];
if (
	!whitelist.includes(node.nodeName.toUpperCase()) &&
	axe.commons.dom.hasContentVirtual(virtualNode)
) {
	const styles = window.getComputedStyle(node);
	if (styles.getPropertyValue('display') === 'none') {
		return undefined;
	} else if (styles.getPropertyValue('visibility') === 'hidden') {
		// Check if visibility isn't inherited
		const parent = axe.commons.dom.getComposedParent(node);
		const parentStyle = parent && window.getComputedStyle(parent);
		if (
			!parentStyle ||
			parentStyle.getPropertyValue('visibility') !== 'hidden'
		) {
			return undefined;
		}
	}
}
return true;
