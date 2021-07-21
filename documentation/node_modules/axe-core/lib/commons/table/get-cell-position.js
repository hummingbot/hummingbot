/* global table, dom */

/**
 * Get the x, y coordinates of a table cell; normalized for rowspan and colspan
 * @method getCellPosition
 * @memberof axe.commons.table
 * @instance
 * @param  {HTMLTableCellElement} cell The table cell of which to get the position
 * @return {Object} Object with `x` and `y` properties of the coordinates
 */
table.getCellPosition = axe.utils.memoize(function(cell, tableGrid) {
	var rowIndex, index;
	if (!tableGrid) {
		tableGrid = table.toGrid(dom.findUp(cell, 'table'));
	}

	for (rowIndex = 0; rowIndex < tableGrid.length; rowIndex++) {
		if (tableGrid[rowIndex]) {
			index = tableGrid[rowIndex].indexOf(cell);
			if (index !== -1) {
				return {
					x: index,
					y: rowIndex
				};
			}
		}
	}
});
