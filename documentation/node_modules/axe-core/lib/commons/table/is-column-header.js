/* global table */

/**
 * Determine if a `HTMLTableCellElement` is a column header
 * @method isColumnHeader
 * @memberof axe.commons.table
 * @instance
 * @param  {HTMLTableCellElement} element The table cell to test
 * @return {Boolean}
 */
table.isColumnHeader = function(element) {
	return ['col', 'auto'].indexOf(table.getScope(element)) !== -1;
};
