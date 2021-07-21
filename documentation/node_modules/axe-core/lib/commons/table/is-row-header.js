/* global table */

/**
 * Determine if a `HTMLTableCellElement` is a row header
 * @method isRowHeader
 * @memberof axe.commons.table
 * @instance
 * @param  {HTMLTableCellElement} cell The table cell to test
 * @return {Boolean}
 */
table.isRowHeader = function(cell) {
	return ['row', 'auto'].includes(table.getScope(cell));
};
