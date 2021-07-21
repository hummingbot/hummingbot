/*global CheckResult,DqElement */

function createExecutionContext(spec) {
	/*eslint no-eval:0 */
	'use strict';
	if (typeof spec === 'string') {
		return new Function('return ' + spec + ';')();
	}
	return spec;
}

function Check(spec) {
	if (spec) {
		this.id = spec.id;
		this.configure(spec);
	}
}

/**
 * Unique ID for the check.  Checks may be re-used, so there may be additional instances of checks
 * with the same ID.
 * @type {String}
 */
// Check.prototype.id;

/**
 * Free-form options that are passed as the second parameter to the `evaluate`
 * @type {Mixed}
 */
// Check.prototype.options;

/**
 * The actual code, accepts 2 parameters: node (the node under test), options (see this.options).
 * This function is run in the context of a checkHelper, which has the following methods
 * - `async()` - if called, the check is considered to be asynchronous; returns a callback function
 * - `data()` - free-form data object, associated to the `CheckResult` which is specific to each node
 * @type {Function}
 */
// Check.prototype.evaluate;

/**
 * Optional. Filter and/or modify checks for all nodes
 * @type {Function}
 */
// Check.prototype.after;

/**
 * enabled by default, if false, this check will not be included in the rule's evaluation
 * @type {Boolean}
 */
Check.prototype.enabled = true;

/**
 * Run the check's evaluate function (call `this.evaluate(node, options)`)
 * @param  {HTMLElement} node  The node to test
 * @param  {Object} options    The options that override the defaults and provide additional
 *                             information for the check
 * @param  {Function} callback Function to fire when check is complete
 */
Check.prototype.run = function(node, options, context, resolve, reject) {
	'use strict';
	options = options || {};
	var enabled = options.hasOwnProperty('enabled')
			? options.enabled
			: this.enabled,
		checkOptions = options.options || this.options;

	if (enabled) {
		var checkResult = new CheckResult(this);
		var checkHelper = axe.utils.checkHelper(
			checkResult,
			options,
			resolve,
			reject
		);
		var result;

		try {
			result = this.evaluate.call(
				checkHelper,
				node.actualNode,
				checkOptions,
				node,
				context
			);
		} catch (e) {
			// In the "Audit#run: should run all the rules" test, there is no `node` here. I do
			// not know if this is intentional or not, so to be safe, we guard against the
			// possible reference error.
			if (node && node.actualNode) {
				// Save a reference to the node we errored on for futher debugging.
				e.errorNode = new DqElement(node.actualNode).toJSON();
			}
			reject(e);
			return;
		}

		if (!checkHelper.isAsync) {
			checkResult.result = result;
			resolve(checkResult);
		}
	} else {
		resolve(null);
	}
};

/**
 * Run the check's evaluate function (call `this.evaluate(node, options)`) synchronously
 * @param  {HTMLElement} node  The node to test
 * @param  {Object} options    The options that override the defaults and provide additional
 *                             information for the check
 */
Check.prototype.runSync = function(node, options, context) {
	options = options || {};
	const { enabled = this.enabled } = options;

	if (!enabled) {
		return null;
	}

	const checkOptions = options.options || this.options;
	const checkResult = new CheckResult(this);
	const checkHelper = axe.utils.checkHelper(checkResult, options);

	// throw error if a check is run that requires async behavior
	checkHelper.async = function() {
		throw new Error('Cannot run async check while in a synchronous run');
	};

	let result;

	try {
		result = this.evaluate.call(
			checkHelper,
			node.actualNode,
			checkOptions,
			node,
			context
		);
	} catch (e) {
		// In the "Audit#run: should run all the rules" test, there is no `node` here. I do
		// not know if this is intentional or not, so to be safe, we guard against the
		// possible reference error.
		if (node && node.actualNode) {
			// Save a reference to the node we errored on for futher debugging.
			e.errorNode = new DqElement(node.actualNode).toJSON();
		}
		throw e;
	}

	checkResult.result = result;
	return checkResult;
};

/**
 * Override a check's settings after construction to allow for changing options
 * without having to implement the entire check
 *
 * @param {Object} spec - the specification of the attributes to be changed
 */

Check.prototype.configure = function(spec) {
	['options', 'enabled']
		.filter(prop => spec.hasOwnProperty(prop))
		.forEach(prop => (this[prop] = spec[prop]));

	['evaluate', 'after']
		.filter(prop => spec.hasOwnProperty(prop))
		.forEach(prop => (this[prop] = createExecutionContext(spec[prop])));
};
