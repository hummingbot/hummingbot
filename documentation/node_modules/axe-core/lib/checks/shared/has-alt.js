const { nodeName } = virtualNode.props;
if (!['img', 'input', 'area'].includes(nodeName)) {
	return false;
}

return virtualNode.hasAttr('alt');
