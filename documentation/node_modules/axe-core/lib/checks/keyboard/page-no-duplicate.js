if (!options || !options.selector || typeof options.selector !== 'string') {
	throw new TypeError(
		'visible-in-page requires options.selector to be a string'
	);
}

// only look at the first node and it's related nodes
const key = 'page-no-duplicate;' + options.selector;
if (axe._cache.get(key)) {
	this.data('ignored');
	return;
}
axe._cache.set(key, true);

let elms = axe.utils.querySelectorAllFilter(
	axe._tree[0],
	options.selector,
	elm => axe.commons.dom.isVisible(elm.actualNode)
);

// Filter elements that, within certain contexts, don't map their role.
// e.g. a <footer> inside a <main> is not a banner, but in the <body> context it is
if (typeof options.nativeScopeFilter === 'string') {
	elms = elms.filter(elm => {
		return (
			elm.actualNode.hasAttribute('role') ||
			!axe.commons.dom.findUpVirtual(elm, options.nativeScopeFilter)
		);
	});
}

this.relatedNodes(
	elms.filter(elm => elm !== virtualNode).map(elm => elm.actualNode)
);

return elms.length <= 1;
