var role = (node.getAttribute('role') || '').toLowerCase();

return (
	!(
		(role === 'presentation' || role === 'none') &&
		!axe.commons.dom.isFocusable(node)
	) && !axe.commons.table.isDataTable(node)
);
