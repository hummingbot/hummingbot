/* global axe*/

/**
 * Get the pass, fail, or incomplete message for a check.
 * @param {String} checkId The check id
 * @param {String} type The message type ('pass', 'fail', or 'incomplete')
 * @param {Object} [data] The check data
 * @return {String}
 */
axe.utils.getCheckMessage = function getCheckMessage(checkId, type, data) {
	const check = axe._audit.data.checks[checkId];

	if (!check) {
		throw new Error(`Cannot get message for unknown check: ${checkId}.`);
	}
	if (!check.messages[type]) {
		throw new Error(`Check "${checkId}"" does not have a "${type}" message.`);
	}

	return axe.utils.processMessage(check.messages[type], data);
};
