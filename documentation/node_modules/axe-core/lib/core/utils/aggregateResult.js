function copyToGroup(resultObject, subResult, group) {
	var resultCopy = Object.assign({}, subResult);
	resultCopy.nodes = (resultCopy[group] || []).concat();
	axe.constants.resultGroups.forEach(group => {
		delete resultCopy[group];
	});
	resultObject[group].push(resultCopy);
}

/**
 * Calculates the result of a Rule based on its types and the result of its child Checks
 * @param  {RuleResult} ruleResult The RuleResult to calculate the result of
 */
axe.utils.aggregateResult = function(results) {
	let resultObject = {};

	// Create an array for each type
	axe.constants.resultGroups.forEach(
		groupName => (resultObject[groupName] = [])
	);

	// Fill the array with nodes
	results.forEach(function(subResult) {
		if (subResult.error) {
			copyToGroup(resultObject, subResult, axe.constants.CANTTELL_GROUP);
		} else if (subResult.result === axe.constants.NA) {
			copyToGroup(resultObject, subResult, axe.constants.NA_GROUP);
		} else {
			axe.constants.resultGroups.forEach(function(group) {
				if (Array.isArray(subResult[group]) && subResult[group].length > 0) {
					copyToGroup(resultObject, subResult, group);
				}
			});
		}
	});
	return resultObject;
};
