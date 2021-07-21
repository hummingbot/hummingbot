/* global table */
(function(table) {
	var traverseTable = function(dir, position, tableGrid, callback) {
		var result;
		var cell = tableGrid[position.y]
			? tableGrid[position.y][position.x]
			: undefined;
		if (!cell) {
			return [];
		}
		if (typeof callback === 'function') {
			result = callback(cell, position, tableGrid);
			if (result === true) {
				// abort
				return [cell];
			}
		}

		result = traverseTable(
			dir,
			{
				x: position.x + dir.x,
				y: position.y + dir.y
			},
			tableGrid,
			callback
		);
		result.unshift(cell);
		return result;
	};

	/**
	 * Traverses a table in a given direction, passing the cell to the callback
	 * @method traverse
	 * @memberof axe.commons.table
	 * @instance
	 * @param  {Object|String} dir Direction that will be added recursively {x: 1, y: 0}, 'left';
	 * @param  {Object}   startPos    x/y coordinate: {x: 0, y: 0};
	 * @param  {Array}    [tablegrid]  A matrix of the table obtained using axe.commons.table.toArray (OPTIONAL)
	 * @param  {Function} callback Function to which each cell will be passed
	 * @return {NodeElement}       If the callback returns true, the traversal will end and the cell will be returned
	 */
	table.traverse = function(dir, startPos, tableGrid, callback) {
		/* eslint indent: 0 */
		if (Array.isArray(startPos)) {
			callback = tableGrid;
			tableGrid = startPos;
			startPos = { x: 0, y: 0 };
		}

		if (typeof dir === 'string') {
			switch (dir) {
				case 'left':
					dir = { x: -1, y: 0 };
					break;
				case 'up':
					dir = { x: 0, y: -1 };
					break;
				case 'right':
					dir = { x: 1, y: 0 };
					break;
				case 'down':
					dir = { x: 0, y: 1 };
					break;
			}
		}

		return traverseTable(
			dir,
			{
				x: startPos.x + dir.x,
				y: startPos.y + dir.y
			},
			tableGrid,
			callback
		);
	};
})(table);
