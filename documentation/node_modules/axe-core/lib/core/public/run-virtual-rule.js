/* global helpers, SerialVirtualNode */

/**
 * Run a rule in a non-browser environment
 * @param {String} ruleId  Id of the rule
 * @param {VirtualNode} vNode  The virtual node to run the rule against
 * @param {Object} options  (optional) Set of options passed into rules or checks
 * @return {Object} axe results for the rule run
 */
axe.runVirtualRule = function(ruleId, vNode, options = {}) {
	options.reporter = options.reporter || axe._audit.reporter || 'v1';
	axe._selectorData = {};

	if (vNode instanceof axe.AbstractVirtualNode === false) {
		vNode = new SerialVirtualNode(vNode);
	}

	let rule = axe._audit.rules.find(rule => rule.id === ruleId);

	if (!rule) {
		throw new Error('unknown rule `' + ruleId + '`');
	}

	// rule.prototype.gather calls axe.utils.isHidden which in turn calls
	// window.getComputedStyle if the rule excludes hidden elements. we
	// can avoid this call by forcing the rule to not exclude hidden
	// elements
	rule = Object.create(rule, { excludeHidden: { value: false } });

	const context = {
		include: [vNode]
	};

	const rawResults = rule.runSync(context, options);
	axe.utils.publishMetaData(rawResults);
	axe.utils.finalizeRuleResult(rawResults);
	const results = axe.utils.aggregateResult([rawResults]);

	results.violations.forEach(result =>
		result.nodes.forEach(nodeResult => {
			nodeResult.failureSummary = helpers.failureSummary(nodeResult);
		})
	);

	return {
		...helpers.getEnvironmentData(),
		...results,
		toolOptions: options
	};
};
