/* global axe*/

/**
 * If the first argument is falsey, throw an error using the second argument as a message.
 * @param {boolean} bool
 * @param {string} message
 */
axe.utils.assert = function assert(bool, message) {
	if (!bool) {
		throw new Error(message);
	}
};
