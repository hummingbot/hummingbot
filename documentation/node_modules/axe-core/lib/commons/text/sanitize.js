/* global text */

/**
 * Removes carriage returns, newline characters, tabs, non-breaking spaces, and trailing spaces from string
 * @method sanitize
 * @memberof axe.commons.text
 * @instance
 * @param  {String} str String to be cleaned
 * @return {String} Sanitized string
 */
text.sanitize = function(str) {
	'use strict';
	return str
		.replace(/\r\n/g, '\n')
		.replace(/\u00A0/g, ' ')
		.replace(/[\s]{2,}/g, ' ')
		.trim();
};
