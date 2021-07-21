if (axe.commons.dom.isVisible(node, false)) {
	this.data(node.getAttribute('accesskey'));
	this.relatedNodes([node]);
}
return true;
