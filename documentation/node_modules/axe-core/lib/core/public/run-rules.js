/*global Context */
/*exported runRules */

// Clean up after resolve / reject
function cleanup() {
	axe._memoizedFns.forEach(fn => fn.clear());
	axe._cache.clear();
	axe._tree = undefined;
	axe._selectorData = undefined;
}

/**
 * Starts analysis on the current document and its subframes
 * @private
 * @param  {Object}   context  The `Context` specification object @see Context
 * @param  {Array}    options  Optional RuleOptions
 * @param  {Function} resolve  Called when done running rules, receives ([results : Object], cleanup : Function)
 * @param  {Function} reject   Called when execution failed, receives (err : Error)
 */
function runRules(context, options, resolve, reject) {
	'use strict';
	try {
		context = new Context(context);
		axe._tree = context.flatTree;
		axe._selectorData = axe.utils.getSelectorData(context.flatTree);
	} catch (e) {
		cleanup();
		return reject(e);
	}

	var q = axe.utils.queue();
	var audit = axe._audit;

	if (options.performanceTimer) {
		axe.utils.performanceTimer.auditStart();
	}

	if (context.frames.length && options.iframes !== false) {
		q.defer(function(res, rej) {
			axe.utils.collectResultsFromFrames(
				context,
				options,
				'rules',
				null,
				res,
				rej
			);
		});
	}
	let scrollState;
	q.defer(function(res, rej) {
		if (options.restoreScroll) {
			scrollState = axe.utils.getScrollState();
		}
		audit.run(context, options, res, rej);
	});
	q.then(function(data) {
		try {
			if (scrollState) {
				axe.utils.setScrollState(scrollState);
			}
			if (options.performanceTimer) {
				axe.utils.performanceTimer.auditEnd();
			}

			// Add wrapper object so that we may use the same "merge" function for results from inside and outside frames
			var results = axe.utils.mergeResults(
				data.map(function(results) {
					return { results };
				})
			);

			// after should only run once, so ensure we are in the top level window
			if (context.initiator) {
				results = audit.after(results, options);

				results.forEach(axe.utils.publishMetaData);
				results = results.map(axe.utils.finalizeRuleResult);
			}
			try {
				resolve(results, cleanup);
			} catch (e) {
				cleanup();
				axe.log(e);
			}
		} catch (e) {
			cleanup();
			reject(e);
		}
	}).catch(e => {
		cleanup();
		reject(e);
	});
}

axe._runRules = runRules;
