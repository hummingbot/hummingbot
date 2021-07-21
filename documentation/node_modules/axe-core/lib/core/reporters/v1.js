/*global helpers */

axe.addReporter('v1', function(results, options, callback) {
	'use strict';

	if (typeof options === 'function') {
		callback = options;
		options = {};
	}
	var out = helpers.processAggregate(results, options);

	const addFailureSummaries = result => {
		result.nodes.forEach(nodeResult => {
			nodeResult.failureSummary = helpers.failureSummary(nodeResult);
		});
	};

	out.incomplete.forEach(addFailureSummaries);
	out.violations.forEach(addFailureSummaries);

	callback({
		...helpers.getEnvironmentData(),
		toolOptions: options,
		violations: out.violations,
		passes: out.passes,
		incomplete: out.incomplete,
		inapplicable: out.inapplicable
	});
});
