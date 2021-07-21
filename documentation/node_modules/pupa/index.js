'use strict';
const {htmlEscape} = require('escape-goat');

module.exports = (template, data) => {
	if (typeof template !== 'string') {
		throw new TypeError(`Expected a \`string\` in the first argument, got \`${typeof template}\``);
	}

	if (typeof data !== 'object') {
		throw new TypeError(`Expected an \`object\` or \`Array\` in the second argument, got \`${typeof data}\``);
	}

	// The regex tries to match either a number inside `{{ }}` or a valid JS identifier or key path.
	const doubleBraceRegex = /{{(\d+|[a-z$_][a-z\d$_]*?(?:\.[a-z\d$_]*?)*?)}}/g;

	if (doubleBraceRegex.test(template)) {
		template = template.replace(doubleBraceRegex, (_, key) => {
			let result = data;

			for (const property of key.split('.')) {
				result = result ? result[property] : '';
			}

			return htmlEscape(String(result));
		});
	}

	const braceRegex = /{(\d+|[a-z$_][a-z\d$_]*?(?:\.[a-z\d$_]*?)*?)}/g;

	return template.replace(braceRegex, (_, key) => {
		let result = data;

		for (const property of key.split('.')) {
			result = result ? result[property] : '';
		}

		return String(result);
	});
};
