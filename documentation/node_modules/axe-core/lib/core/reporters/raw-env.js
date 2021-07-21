/*global helpers */
axe.addReporter('rawEnv', function(results, options, callback) {
	if (typeof options === 'function') {
		callback = options;
		options = {};
	}
	function rawCallback(raw) {
		const env = helpers.getEnvironmentData();
		callback({ raw, env });
	}
	axe.getReporter('raw')(results, options, rawCallback);
});
