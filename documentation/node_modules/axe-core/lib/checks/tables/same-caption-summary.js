// passing node.caption to accessibleText instead of using
// the logic in accessibleTextVirtual on virtualNode
return (
	!!(node.summary && node.caption) &&
	node.summary.toLowerCase() ===
		axe.commons.text.accessibleText(node.caption).toLowerCase()
);
