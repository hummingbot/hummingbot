if (axe.commons.table.isDataTable(node)) {
	var tableArray = axe.commons.table.toArray(node);
	return (
		tableArray.length >= 3 &&
		tableArray[0].length >= 3 &&
		tableArray[1].length >= 3 &&
		tableArray[2].length >= 3
	);
}

return false;
