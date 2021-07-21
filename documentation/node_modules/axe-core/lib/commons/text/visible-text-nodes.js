/* global text */

/**
 * Returns an array of visible text virtual nodes

 * @method visibleTextNodes
 * @memberof axe.commons.text
 * @instance
 * @param {VirtualNode} vNode
 * @return {VitrualNode[]}
 */
text.visibleTextNodes = function(vNode) {
	const parentVisible = axe.commons.dom.isVisible(vNode.actualNode);
	let nodes = [];
	vNode.children.forEach(child => {
		if (child.actualNode.nodeType === 3) {
			if (parentVisible) {
				nodes.push(child);
			}
		} else {
			nodes = nodes.concat(text.visibleTextNodes(child));
		}
	});
	return nodes;
};
