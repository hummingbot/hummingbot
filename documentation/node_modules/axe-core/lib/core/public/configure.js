/* global reporters */
function configureChecksRulesAndBranding(spec) {
	'use strict';
	var audit;

	audit = axe._audit;
	if (!audit) {
		throw new Error('No audit configured');
	}

	if (spec.axeVersion || spec.ver) {
		let specVersion = spec.axeVersion || spec.ver;
		if (!/^\d+\.\d+\.\d+(-canary)?/.test(specVersion)) {
			throw new Error(`Invalid configured version ${specVersion}`);
		}

		let [version, canary] = specVersion.split('-');
		let [major, minor, patch] = version.split('.').map(Number);

		let [axeVersion, axeCanary] = axe.version.split('-');
		let [axeMajor, axeMinor, axePatch] = axeVersion.split('.').map(Number);

		if (
			major !== axeMajor ||
			axeMinor < minor ||
			(axeMinor === minor && axePatch < patch) ||
			(major === axeMajor &&
				minor === axeMinor &&
				patch === axePatch &&
				canary &&
				canary !== axeCanary)
		) {
			throw new Error(
				`Configured version ${specVersion} is not compatible with current axe version ${axe.version}`
			);
		}
	}

	if (
		spec.reporter &&
		(typeof spec.reporter === 'function' || reporters[spec.reporter])
	) {
		audit.reporter = spec.reporter;
	}

	if (spec.checks) {
		if (!Array.isArray(spec.checks)) {
			throw new TypeError('Checks property must be an array');
		}

		spec.checks.forEach(function(check) {
			if (!check.id) {
				throw new TypeError(
					// eslint-disable-next-line max-len
					`Configured check ${JSON.stringify(
						check
					)} is invalid. Checks must be an object with at least an id property`
				);
			}

			audit.addCheck(check);
		});
	}

	const modifiedRules = [];
	if (spec.rules) {
		if (!Array.isArray(spec.rules)) {
			throw new TypeError('Rules property must be an array');
		}

		spec.rules.forEach(function(rule) {
			if (!rule.id) {
				throw new TypeError(
					// eslint-disable-next-line max-len
					`Configured rule ${JSON.stringify(
						rule
					)} is invalid. Rules must be an object with at least an id property`
				);
			}

			modifiedRules.push(rule.id);
			audit.addRule(rule);
		});
	}

	if (spec.disableOtherRules) {
		audit.rules.forEach(rule => {
			if (modifiedRules.includes(rule.id) === false) {
				rule.enabled = false;
			}
		});
	}

	if (typeof spec.branding !== 'undefined') {
		audit.setBranding(spec.branding);
	} else {
		audit._constructHelpUrls();
	}

	if (spec.tagExclude) {
		audit.tagExclude = spec.tagExclude;
	}

	// Support runtime localization
	if (spec.locale) {
		audit.applyLocale(spec.locale);
	}
}

axe.configure = configureChecksRulesAndBranding;
