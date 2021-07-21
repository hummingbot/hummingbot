const titleNode = virtualNode.children.find(({ props }) => {
	return props.nodeName === 'title';
});
return !!titleNode && titleNode.actualNode.textContent.trim() !== '';
