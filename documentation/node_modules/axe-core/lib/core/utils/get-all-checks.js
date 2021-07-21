/**
 * Gets all Checks (or CheckResults) for a given Rule or RuleResult
 * @param {RuleResult|Rule} rule
 */
axe.utils.getAllChecks = function getAllChecks(object) {
	'use strict';
	var result = [];
	return result
		.concat(object.any || [])
		.concat(object.all || [])
		.concat(object.none || []);
};
