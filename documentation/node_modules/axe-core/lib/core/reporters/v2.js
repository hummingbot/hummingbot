/*global helpers */

axe.addReporter(
	'v2',
	function(results, options, callback) {
		'use strict';
		if (typeof options === 'function') {
			callback = options;
			options = {};
		}
		var out = helpers.processAggregate(results, options);
		callback({
			...helpers.getEnvironmentData(),
			toolOptions: options,
			violations: out.violations,
			passes: out.passes,
			incomplete: out.incomplete,
			inapplicable: out.inapplicable
		});
	},
	true
);
