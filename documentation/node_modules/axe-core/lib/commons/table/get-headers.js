/* global table */

/**
 * Loop through the table grid looking for headers and caching the result.
 * @param {String} headerType The type of header to look for ("row" or "col")
 * @param {Object} position The position of the cell to start looking
 * @param {Array} tablegrid A matrix of the table obtained using axe.commons.table.toGrid
 * @return {Array<HTMLTableCellElement>} Array of HTMLTableCellElements that are headers
 */
function traverseForHeaders(headerType, position, tableGrid) {
	const property = headerType === 'row' ? '_rowHeaders' : '_colHeaders';
	const predicate =
		headerType === 'row' ? table.isRowHeader : table.isColumnHeader;
	const rowEnd = headerType === 'row' ? position.y : 0;
	const colEnd = headerType === 'row' ? 0 : position.x;

	let headers;
	const cells = [];
	for (let row = position.y; row >= rowEnd && !headers; row--) {
		for (let col = position.x; col >= colEnd; col--) {
			const cell = tableGrid[row] ? tableGrid[row][col] : undefined;

			if (!cell) {
				continue;
			}

			// stop traversing once we've found a cache
			const vNode = axe.utils.getNodeFromTree(cell);
			if (vNode[property]) {
				headers = vNode[property];
				break;
			}

			cells.push(cell);
		}
	}

	// need to check that the cells we've traversed are headers
	headers = (headers || []).concat(cells.filter(predicate));

	// cache results
	cells.forEach(tableCell => {
		const vNode = axe.utils.getNodeFromTree(tableCell);
		vNode[property] = headers;
	});

	return headers;
}

/**
 * Get any associated table headers for a `HTMLTableCellElement`
 * @method getHeaders
 * @memberof axe.commons.table
 * @instance
 * @param  {HTMLTableCellElement} cell The cell of which to get headers
 * @param {Array} [tablegrid] A matrix of the table obtained using axe.commons.table.toGrid
 * @return {Array<HTMLTableCellElement>} Array of headers associated to the table cell
 */
table.getHeaders = function(cell, tableGrid) {
	if (cell.getAttribute('headers')) {
		const headers = commons.dom.idrefs(cell, 'headers');

		// testing has shown that if the headers attribute is incorrect the browser
		// will default to the table row/column headers
		if (headers.filter(header => header).length) {
			return headers;
		}
	}
	if (!tableGrid) {
		tableGrid = commons.table.toGrid(commons.dom.findUp(cell, 'table'));
	}
	const position = commons.table.getCellPosition(cell, tableGrid);

	// TODO: RTL text
	const rowHeaders = traverseForHeaders('row', position, tableGrid);
	const colHeaders = traverseForHeaders('col', position, tableGrid);

	return [].concat(rowHeaders, colHeaders).reverse();
};
