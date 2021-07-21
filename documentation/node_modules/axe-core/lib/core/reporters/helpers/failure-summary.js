/*global helpers */

/**
 * Finds failing Checks and combines each help message into an array
 * @param  {Object} nodeData Individual "detail" object to generate help messages for
 * @return {String}          failure messages
 */
helpers.failureSummary = function failureSummary(nodeData) {
	'use strict';

	var failingChecks = {};
	// combine "all" and "none" as messaging is the same
	failingChecks.none = nodeData.none.concat(nodeData.all);
	failingChecks.any = nodeData.any;

	return Object.keys(failingChecks)
		.map(function(key) {
			if (!failingChecks[key].length) {
				return;
			}

			var sum = axe._audit.data.failureSummaries[key];
			if (sum && typeof sum.failureMessage === 'function') {
				return sum.failureMessage(
					failingChecks[key].map(function(check) {
						return check.message || '';
					})
				);
			}
		})
		.filter(function(i) {
			return i !== undefined;
		})
		.join('\n\n');
};
