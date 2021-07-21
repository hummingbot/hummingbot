if (!options || !options.selector || typeof options.selector !== 'string') {
	throw new TypeError(
		'visible-in-page requires options.selector to be a string'
	);
}

const matchingElms = axe.utils.querySelectorAllFilter(
	virtualNode,
	options.selector,
	vNode => axe.commons.dom.isVisible(vNode.actualNode, true)
);
this.relatedNodes(matchingElms.map(vNode => vNode.actualNode));
return matchingElms.length > 0;
