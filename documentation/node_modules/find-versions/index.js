'use strict';
const semverRegex = require('semver-regex');

module.exports = (stringWithVersions, options = {}) => {
	if (typeof stringWithVersions !== 'string') {
		throw new TypeError(`Expected a string, got ${typeof stringWithVersions}`);
	}

	const reLoose = new RegExp(`(?:${semverRegex().source})|(?:v?(?:\\d+\\.\\d+)(?:\\.\\d+)?)`, 'g');
	const matches = stringWithVersions.match(options.loose === true ? reLoose : semverRegex()) || [];

	return [...new Set(matches.map(match => match.trim().replace(/^v/, '').replace(/^\d+\.\d+$/, '$&.0')))];
};
