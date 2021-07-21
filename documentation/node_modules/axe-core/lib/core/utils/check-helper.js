/**
 * Helper to denote which checks are asyncronous and provide callbacks and pass data back to the CheckResult
 * @param  {CheckResult}   checkResult The target object
 * @param  {Function} callback    The callback to expose when `this.async()` is called
 * @return {Object}               Bound to `this` for a check's fn
 */
axe.utils.checkHelper = function checkHelper(
	checkResult,
	options,
	resolve,
	reject
) {
	'use strict';

	return {
		isAsync: false,
		async: function() {
			this.isAsync = true;
			return function(result) {
				if (result instanceof Error === false) {
					checkResult.result = result;
					resolve(checkResult);
				} else {
					reject(result);
				}
			};
		},
		data: function(data) {
			checkResult.data = data;
		},
		relatedNodes: function(nodes) {
			nodes = nodes instanceof Node ? [nodes] : axe.utils.toArray(nodes);
			checkResult.relatedNodes = nodes.map(function(element) {
				return new axe.utils.DqElement(element, options);
			});
		}
	};
};
