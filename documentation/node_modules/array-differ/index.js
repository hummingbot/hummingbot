'use strict';

const arrayDiffer = (array, ...values) => {
	const rest = new Set([].concat(...values));
	return array.filter(element => !rest.has(element));
};

module.exports = arrayDiffer;
