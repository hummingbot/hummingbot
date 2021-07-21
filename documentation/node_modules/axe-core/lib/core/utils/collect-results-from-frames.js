function err(message, node) {
	'use strict';
	var selector;
	if (axe._tree) {
		selector = axe.utils.getSelector(node);
	}
	return new Error(message + ': ' + (selector || node));
}

/**
 * Sends a command to an instance of axe in the specified frame
 * @param  {Element}  node       The frame element to send the message to
 * @param  {Object}   parameters Parameters to pass to the frame
 * @param  {Function} callback   Function to call when results from the frame has returned
 */
axe.utils.sendCommandToFrame = function(node, parameters, resolve, reject) {
	'use strict';

	var win = node.contentWindow;
	if (!win) {
		axe.log('Frame does not have a content window', node);
		resolve(null);
		return;
	}

	// give the frame .5s to respond to 'axe.ping', else log failed response
	var timeout = setTimeout(function() {
		// This double timeout is important for allowing iframes to respond
		// DO NOT REMOVE
		timeout = setTimeout(function() {
			if (!parameters.debug) {
				resolve(null);
			} else {
				reject(err('No response from frame', node));
			}
		}, 0);
	}, 500);

	// send 'axe.ping' to the frame
	axe.utils.respondable(win, 'axe.ping', null, undefined, function() {
		clearTimeout(timeout);

		// Give axe 60s (or user-supplied value) to respond to 'axe.start'
		var frameWaitTime =
			(parameters.options && parameters.options.frameWaitTime) || 60000;

		timeout = setTimeout(function collectResultFramesTimeout() {
			reject(err('Axe in frame timed out', node));
		}, frameWaitTime);

		// send 'axe.start' and send the callback if it responded
		axe.utils.respondable(win, 'axe.start', parameters, undefined, function(
			data
		) {
			clearTimeout(timeout);
			if (data instanceof Error === false) {
				resolve(data);
			} else {
				reject(data);
			}
		});
	});
};

/**
 * Sends a message to axe running in frames to start analysis and collate results (via `mergeResults`)
 * @private
 * @param  {Context}  context   The resolved Context object
 * @param  {Object}   options   Options object (as passed to `runRules`)
 * @param  {string}   command   Command sent to all frames
 * @param  {Array}    parameter Array of values to be passed along side the command
 * @param  {Function} callback  Function to call when results from all frames have returned
 */
function collectResultsFromFrames(
	context,
	options,
	command,
	parameter,
	resolve,
	reject
) {
	'use strict';

	var q = axe.utils.queue();
	var frames = context.frames;

	// Tell each axe running in each frame to collect results
	frames.forEach(function(frame) {
		var params = {
			options: options,
			command: command,
			parameter: parameter,
			context: {
				initiator: false,
				page: context.page,
				include: frame.include || [],
				exclude: frame.exclude || []
			}
		};

		q.defer(function(res, rej) {
			var node = frame.node;
			axe.utils.sendCommandToFrame(
				node,
				params,
				function(data) {
					if (data) {
						return res({
							results: data,
							frameElement: node,
							frame: axe.utils.getSelector(node)
						});
					}
					res(null);
				},
				rej
			);
		});
	});

	// Combine results from all frames and give it back
	q.then(function(data) {
		resolve(axe.utils.mergeResults(data, options));
	}).catch(reject);
}

axe.utils.collectResultsFromFrames = collectResultsFromFrames;
