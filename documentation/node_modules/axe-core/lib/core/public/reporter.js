var reporters = {};
var defaultReporter;

axe.getReporter = function(reporter) {
	'use strict';
	if (typeof reporter === 'string' && reporters[reporter]) {
		return reporters[reporter];
	}

	if (typeof reporter === 'function') {
		return reporter;
	}

	return defaultReporter;
};

axe.addReporter = function registerReporter(name, cb, isDefault) {
	'use strict';

	reporters[name] = cb;
	if (isDefault) {
		defaultReporter = cb;
	}
};
