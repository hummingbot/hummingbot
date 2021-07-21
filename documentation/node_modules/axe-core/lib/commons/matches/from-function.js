/* global matches */

/**
 * Check if the value from a function matches some condition
 *
 * Each key on the matcher object is passed to getValue, the returned value must match
 * with the value of that matcher
 *
 * Example:
 * ```js
 * matches.fromFunction(
 * 	 (attr => node.getAttribute(attr),
 * 	 {
 * 	   'aria-hidden': /^true|false$/i
 * 	 }
 * )
 * ```
 *
 * @private
 * @param {Function} getValue
 * @param {Object} matcher matcher
 * @returns {Boolean}
 */
matches.fromFunction = function matchFromFunction(getValue, matcher) {
	const matcherType = typeof matcher;
	if (
		matcherType !== 'object' ||
		Array.isArray(matcher) ||
		matcher instanceof RegExp
	) {
		throw new Error('Expect matcher to be an object');
	}

	// Check that the property has all the expected values
	return Object.keys(matcher).every(propName => {
		return matches.fromPrimative(getValue(propName), matcher[propName]);
	});
};
