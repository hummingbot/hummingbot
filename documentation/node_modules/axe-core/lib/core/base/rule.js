/*global RuleResult, createExecutionContext, SupportError */

function Rule(spec, parentAudit) {
	'use strict';

	this._audit = parentAudit;

	/**
	 * The code, or string ID of the rule
	 * @type {String}
	 */
	this.id = spec.id;

	/**
	 * Selector that this rule applies to
	 * @type {String}
	 */
	this.selector = spec.selector || '*';

	/**
	 * Whether to exclude hiddden elements form analysis.  Defaults to true.
	 * @type {Boolean}
	 */
	this.excludeHidden =
		typeof spec.excludeHidden === 'boolean' ? spec.excludeHidden : true;

	/**
	 * Flag to enable or disable rule
	 * @type {Boolean}
	 */
	this.enabled = typeof spec.enabled === 'boolean' ? spec.enabled : true;

	/**
	 * Denotes if the rule should be run if Context is not an entire page AND whether
	 * the Rule should be satisified regardless of Node
	 * @type {Boolean}
	 */
	this.pageLevel = typeof spec.pageLevel === 'boolean' ? spec.pageLevel : false;

	/**
	 * Checks that any may return true to satisfy rule
	 * @type {Array}
	 */
	this.any = spec.any || [];

	/**
	 * Checks that must all return true to satisfy rule
	 * @type {Array}
	 */
	this.all = spec.all || [];

	/**
	 * Checks that none may return true to satisfy rule
	 * @type {Array}
	 */
	this.none = spec.none || [];

	/**
	 * Tags associated to this rule
	 * @type {Array}
	 */
	this.tags = spec.tags || [];

	/**
	 * Preload necessary for this rule
	 */
	this.preload = spec.preload ? true : false;

	if (spec.matches) {
		/**
		 * Optional function to test if rule should be run against a node, overrides Rule#matches
		 * @type {Function}
		 */
		this.matches = createExecutionContext(spec.matches);
	}
}

/**
 * Optionally test each node against a `matches` function to determine if the rule should run against
 * a given node.  Defaults to `true`.
 * @return {Boolean}    Whether the rule should run
 */
Rule.prototype.matches = function() {
	'use strict';

	return true;
};

/**
 * Selects `HTMLElement`s based on configured selector
 * @param  {Context} context The resolved Context object
 * @param  {Mixed}   options Options specific to this rule
 * @return {Array}           All matching `HTMLElement`s
 */
Rule.prototype.gather = function(context, options = {}) {
	const markStart = 'mark_gather_start_' + this.id;
	const markEnd = 'mark_gather_end_' + this.id;
	const markHiddenStart = 'mark_isHidden_start_' + this.id;
	const markHiddenEnd = 'mark_isHidden_end_' + this.id;

	if (options.performanceTimer) {
		axe.utils.performanceTimer.mark(markStart);
	}

	var elements = axe.utils.select(this.selector, context);
	if (this.excludeHidden) {
		if (options.performanceTimer) {
			axe.utils.performanceTimer.mark(markHiddenStart);
		}

		elements = elements.filter(function(element) {
			return !axe.utils.isHidden(element.actualNode);
		});

		if (options.performanceTimer) {
			axe.utils.performanceTimer.mark(markHiddenEnd);
			axe.utils.performanceTimer.measure(
				'rule_' + this.id + '#gather_axe.utils.isHidden',
				markHiddenStart,
				markHiddenEnd
			);
		}
	}

	if (options.performanceTimer) {
		axe.utils.performanceTimer.mark(markEnd);
		axe.utils.performanceTimer.measure(
			'rule_' + this.id + '#gather',
			markStart,
			markEnd
		);
	}

	return elements;
};

Rule.prototype.runChecks = function(
	type,
	node,
	options,
	context,
	resolve,
	reject
) {
	'use strict';

	var self = this;

	var checkQueue = axe.utils.queue();

	this[type].forEach(function(c) {
		var check = self._audit.checks[c.id || c];
		var option = axe.utils.getCheckOption(check, self.id, options);
		checkQueue.defer(function(res, rej) {
			check.run(node, option, context, res, rej);
		});
	});

	checkQueue
		.then(function(results) {
			results = results.filter(function(check) {
				return check;
			});
			resolve({ type: type, results: results });
		})
		.catch(reject);
};

/**
 * Run a check for a rule synchronously.
 */
Rule.prototype.runChecksSync = function(type, node, options, context) {
	'use strict';

	const self = this;
	let results = [];

	this[type].forEach(function(c) {
		const check = self._audit.checks[c.id || c];
		const option = axe.utils.getCheckOption(check, self.id, options);
		results.push(check.runSync(node, option, context));
	});

	results = results.filter(function(check) {
		return check;
	});

	return { type: type, results: results };
};

/**
 * Runs the Rule's `evaluate` function
 * @param  {Context}   context  The resolved Context object
 * @param  {Mixed}   options  Options specific to this rule
 * @param  {Function} callback Function to call when evaluate is complete; receives a RuleResult instance
 */
Rule.prototype.run = function(context, options = {}, resolve, reject) {
	if (options.performanceTimer) {
		this._trackPerformance();
	}

	const q = axe.utils.queue();
	const ruleResult = new RuleResult(this);
	let nodes;

	try {
		// Matches throws an error when it lacks support for document methods
		nodes = this.gatherAndMatchNodes(context, options);
	} catch (error) {
		// Exit the rule execution if matches fails
		reject(new SupportError({ cause: error, ruleId: this.id }));
		return;
	}

	if (options.performanceTimer) {
		this._logGatherPerformance(nodes);
	}

	nodes.forEach(node => {
		q.defer((resolveNode, rejectNode) => {
			var checkQueue = axe.utils.queue();

			['any', 'all', 'none'].forEach(type => {
				checkQueue.defer((res, rej) => {
					this.runChecks(type, node, options, context, res, rej);
				});
			});

			checkQueue
				.then(function(results) {
					const result = getResult(results);
					if (result) {
						result.node = new axe.utils.DqElement(node.actualNode, options);
						ruleResult.nodes.push(result);
					}
					resolveNode();
				})
				.catch(err => rejectNode(err));
		});
	});

	// Defer the rule's execution to prevent "unresponsive script" warnings.
	// See https://github.com/dequelabs/axe-core/pull/1172 for discussion and details.
	q.defer(resolve => setTimeout(resolve, 0));

	if (options.performanceTimer) {
		this._logRulePerformance();
	}

	q.then(() => resolve(ruleResult)).catch(error => reject(error));
};

/**
 * Runs the Rule's `evaluate` function synchronously
 * @param  {Context}   context  The resolved Context object
 * @param  {Mixed}   options  Options specific to this rule
 */
Rule.prototype.runSync = function(context, options = {}) {
	if (options.performanceTimer) {
		this._trackPerformance();
	}

	const ruleResult = new RuleResult(this);
	let nodes;

	try {
		nodes = this.gatherAndMatchNodes(context, options);
	} catch (error) {
		// Exit the rule execution if matches fails
		throw new SupportError({ cause: error, ruleId: this.id });
	}

	if (options.performanceTimer) {
		this._logGatherPerformance(nodes);
	}

	nodes.forEach(node => {
		let results = [];
		['any', 'all', 'none'].forEach(type => {
			results.push(this.runChecksSync(type, node, options, context));
		});

		const result = getResult(results);
		if (result) {
			result.node = node.actualNode
				? new axe.utils.DqElement(node.actualNode, options)
				: null;
			ruleResult.nodes.push(result);
		}
	});

	if (options.performanceTimer) {
		this._logRulePerformance();
	}

	return ruleResult;
};

/**
 * Add performance tracking properties to the rule
 * @private
 */
Rule.prototype._trackPerformance = function() {
	this._markStart = 'mark_rule_start_' + this.id;
	this._markEnd = 'mark_rule_end_' + this.id;
	this._markChecksStart = 'mark_runchecks_start_' + this.id;
	this._markChecksEnd = 'mark_runchecks_end_' + this.id;
};

/**
 * Log performance of rule.gather
 * @private
 * @param {Rule} rule The rule to log
 * @param {Array} nodes Result of rule.gather
 */
Rule.prototype._logGatherPerformance = function(nodes) {
	axe.log(
		'gather (',
		nodes.length,
		'):',
		axe.utils.performanceTimer.timeElapsed() + 'ms'
	);
	axe.utils.performanceTimer.mark(this._markChecksStart);
};

/**
 * Log performance of the rule
 * @private
 * @param {Rule} rule The rule to log
 */
Rule.prototype._logRulePerformance = function() {
	axe.utils.performanceTimer.mark(this._markChecksEnd);
	axe.utils.performanceTimer.mark(this._markEnd);
	axe.utils.performanceTimer.measure(
		'runchecks_' + this.id,
		this._markChecksStart,
		this._markChecksEnd
	);

	axe.utils.performanceTimer.measure(
		'rule_' + this.id,
		this._markStart,
		this._markEnd
	);
};

/**
 * Process the results of each check and return the result if a check
 * has a result
 * @private
 * @param {Array} results  Array of each check result
 * @returns {Object|null}
 */
function getResult(results) {
	if (results.length) {
		let hasResults = false,
			result = {};
		results.forEach(function(r) {
			const res = r.results.filter(function(result) {
				return result;
			});
			result[r.type] = res;
			if (res.length) {
				hasResults = true;
			}
		});

		if (hasResults) {
			return result;
		}

		return null;
	}
}

/**
 * Selects `HTMLElement`s based on configured selector and filters them based on
 * the rules matches function
 * @param  {Rule} rule The rule to check for after checks
 * @param  {Context} context The resolved Context object
 * @param  {Mixed}   options Options specific to this rule
 * @return {Array}           All matching `HTMLElement`s
 */
Rule.prototype.gatherAndMatchNodes = function(context, options) {
	const markMatchesStart = 'mark_matches_start_' + this.id;
	const markMatchesEnd = 'mark_matches_end_' + this.id;

	let nodes = this.gather(context, options);

	if (options.performanceTimer) {
		axe.utils.performanceTimer.mark(markMatchesStart);
	}

	nodes = nodes.filter(node => this.matches(node.actualNode, node, context));

	if (options.performanceTimer) {
		axe.utils.performanceTimer.mark(markMatchesEnd);
		axe.utils.performanceTimer.measure(
			'rule_' + this.id + '#matches',
			markMatchesStart,
			markMatchesEnd
		);
	}

	return nodes;
};

/**
 * Iterates the rule's Checks looking for ones that have an after function
 * @private
 * @param  {Rule} rule The rule to check for after checks
 * @return {Array}      Checks that have an after function
 */
function findAfterChecks(rule) {
	'use strict';

	return axe.utils
		.getAllChecks(rule)
		.map(function(c) {
			var check = rule._audit.checks[c.id || c];
			return check && typeof check.after === 'function' ? check : null;
		})
		.filter(Boolean);
}

/**
 * Finds and collates all results for a given Check on a specific Rule
 * @private
 * @param  {Array} nodes RuleResult#nodes; array of 'detail' objects
 * @param  {String} checkID The ID of the Check to find
 * @return {Array}         Matching CheckResults
 */
function findCheckResults(nodes, checkID) {
	'use strict';

	var checkResults = [];
	nodes.forEach(function(nodeResult) {
		var checks = axe.utils.getAllChecks(nodeResult);
		checks.forEach(function(checkResult) {
			if (checkResult.id === checkID) {
				checkResults.push(checkResult);
			}
		});
	});
	return checkResults;
}

function filterChecks(checks) {
	'use strict';

	return checks.filter(function(check) {
		return check.filtered !== true;
	});
}

function sanitizeNodes(result) {
	'use strict';
	var checkTypes = ['any', 'all', 'none'];

	var nodes = result.nodes.filter(function(detail) {
		var length = 0;
		checkTypes.forEach(function(type) {
			detail[type] = filterChecks(detail[type]);
			length += detail[type].length;
		});
		return length > 0;
	});

	if (result.pageLevel && nodes.length) {
		nodes = [
			nodes.reduce(function(a, b) {
				if (a) {
					checkTypes.forEach(function(type) {
						a[type].push.apply(a[type], b[type]);
					});
					return a;
				}
			})
		];
	}
	return nodes;
}

/**
 * Runs all of the Rule's Check#after methods
 * @param  {RuleResult} result  The "pre-after" RuleResult
 * @param  {Mixed} options Options specific to the rule
 * @return {RuleResult}         The RuleResult as filtered by after functions
 */
Rule.prototype.after = function(result, options) {
	'use strict';

	var afterChecks = findAfterChecks(this);
	var ruleID = this.id;
	afterChecks.forEach(function(check) {
		var beforeResults = findCheckResults(result.nodes, check.id);
		var option = axe.utils.getCheckOption(check, ruleID, options);

		var afterResults = check.after(beforeResults, option);
		beforeResults.forEach(function(item) {
			if (afterResults.indexOf(item) === -1) {
				item.filtered = true;
			}
		});
	});

	result.nodes = sanitizeNodes(result);
	return result;
};

/**
 * Reconfigure a rule after it has been added
 * @param {Object} spec - the attributes to be reconfigured
 */
Rule.prototype.configure = function(spec) {
	/*eslint no-eval:0 */
	'use strict';

	if (spec.hasOwnProperty('selector')) {
		this.selector = spec.selector;
	}

	if (spec.hasOwnProperty('excludeHidden')) {
		this.excludeHidden =
			typeof spec.excludeHidden === 'boolean' ? spec.excludeHidden : true;
	}

	if (spec.hasOwnProperty('enabled')) {
		this.enabled = typeof spec.enabled === 'boolean' ? spec.enabled : true;
	}

	if (spec.hasOwnProperty('pageLevel')) {
		this.pageLevel =
			typeof spec.pageLevel === 'boolean' ? spec.pageLevel : false;
	}

	if (spec.hasOwnProperty('any')) {
		this.any = spec.any;
	}

	if (spec.hasOwnProperty('all')) {
		this.all = spec.all;
	}

	if (spec.hasOwnProperty('none')) {
		this.none = spec.none;
	}

	if (spec.hasOwnProperty('tags')) {
		this.tags = spec.tags;
	}

	if (spec.hasOwnProperty('matches')) {
		if (typeof spec.matches === 'string') {
			this.matches = new Function('return ' + spec.matches + ';')();
		} else {
			this.matches = spec.matches;
		}
	}
};
