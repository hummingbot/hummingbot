/*global uuid, utils, axe */
(function(exports) {
	'use strict';
	var messages = {},
		subscribers = {},
		errorTypes = Object.freeze([
			'EvalError',
			'RangeError',
			'ReferenceError',
			'SyntaxError',
			'TypeError',
			'URIError'
		]);

	/**
	 * get the unique string to be used to identify our instance of axe
	 * @private
	 */
	function _getSource() {
		var application = 'axeAPI',
			version = '',
			src;
		if (typeof axe !== 'undefined' && axe._audit && axe._audit.application) {
			application = axe._audit.application;
		}
		if (typeof axe !== 'undefined') {
			version = axe.version;
		}
		src = application + '.' + version;
		return src;
	}
	/**
	 * Verify the received message is from the "respondable" module
	 * @private
	 * @param  {Object} postedMessage The message received via postMessage
	 * @return {Boolean}              `true` if the message is verified from respondable
	 */
	function verify(postedMessage) {
		if (
			// Check incoming message is valid
			typeof postedMessage === 'object' &&
			typeof postedMessage.uuid === 'string' &&
			postedMessage._respondable === true
		) {
			var messageSource = _getSource();
			return (
				// Check the version matches
				postedMessage._source === messageSource ||
				// Allow free communication with axe test
				postedMessage._source === 'axeAPI.x.y.z' ||
				messageSource === 'axeAPI.x.y.z'
			);
		}
		return false;
	}

	/**
	 * Posts the message to correct frame.
	 * This abstraction necessary because IE9 & 10 do not support posting Objects; only strings
	 * @private
	 * @param  {Window}   win      The `window` to post the message to
	 * @param  {String}   topic    The topic of the message
	 * @param  {Object}   message  The message content
	 * @param  {String}   uuid     The UUID, or pseudo-unique ID of the message
	 * @param  {Boolean}  keepalive Whether to allow multiple responses - default is false
	 * @param  {Function} callback The function to invoke when/if the message is responded to
	 */
	function post(win, topic, message, uuid, keepalive, callback) {
		var error;
		if (message instanceof Error) {
			error = {
				name: message.name,
				message: message.message,
				stack: message.stack
			};
			message = undefined;
		}

		var data = {
			uuid: uuid,
			topic: topic,
			message: message,
			error: error,
			_respondable: true,
			_source: _getSource(),
			_axeuuid: axe._uuid,
			_keepalive: keepalive
		};

		var axeRespondables = axe._cache.get('axeRespondables');
		if (!axeRespondables) {
			axeRespondables = {};
			axe._cache.set('axeRespondables', axeRespondables);
		}
		axeRespondables[uuid] = true;
		if (typeof callback === 'function') {
			messages[uuid] = callback;
		}

		win.postMessage(JSON.stringify(data), '*');
	}

	/**
	 * Post a message to a window who may or may not respond to it.
	 * @param  {Window}   win      The window to post the message to
	 * @param  {String}   topic    The topic of the message
	 * @param  {Object}   message  The message content
	 * @param  {Boolean}  keepalive Whether to allow multiple responses - default is false
	 * @param  {Function} callback The function to invoke when/if the message is responded to
	 */
	function respondable(win, topic, message, keepalive, callback) {
		var id = uuid.v1();
		post(win, topic, message, id, keepalive, callback);
	}

	/**
	 * Subscribe to messages sent via the `respondable` module.
	 *
	 * Axe._load uses this to listen for messages from other frames
	 *
	 * @param  {String}   topic    The topic to listen to
	 * @param  {Function} callback The function to invoke when a message is received
	 */
	respondable.subscribe = function(topic, callback) {
		subscribers[topic] = callback;
	};

	/**
	 * checks if the current context is inside a frame
	 * @return {Boolean}
	 */
	respondable.isInFrame = function(win) {
		win = win || window;
		return !!win.frameElement;
	};

	/**
	 * Helper closure to create a function that may be used to respond to a message
	 * @private
	 * @param  {Window} source The window from which the message originated
	 * @param  {String} topic  The topic of the message
	 * @param  {String} uuid   The "unique" ID of the original message
	 * @return {Function}      A function that may be invoked to respond to the message
	 */
	function createResponder(source, topic, uuid) {
		return function(message, keepalive, callback) {
			post(source, topic, message, uuid, keepalive, callback);
		};
	}

	/**
	 * Publishes the "respondable" message to the appropriate subscriber
	 * @private
	 * @param  {Window}  source    The window from which the message originated
	 * @param  {Object}  data      The data sent with the message
	 * @param  {Boolean} keepalive Whether to allow multiple responses - default is false
	 */
	function publish(source, data, keepalive) {
		var topic = data.topic;
		var subscriber = subscribers[topic];

		if (subscriber) {
			var responder = createResponder(source, null, data.uuid);
			subscriber(data.message, keepalive, responder);
		}
	}

	/**
	 * Convert a javascript Error into something that can be stringified
	 * @param  {Error} error  Any type of error
	 * @return {Object}       Processable object
	 */
	function buildErrorObject(error) {
		var msg = error.message || 'Unknown error occurred';
		var errorName = errorTypes.includes(error.name) ? error.name : 'Error';
		var ErrConstructor = window[errorName] || Error;

		if (error.stack) {
			msg += '\n' + error.stack.replace(error.message, '');
		}
		return new ErrConstructor(msg);
	}

	/**
	 * Parse the received message for processing
	 * @param  {string} dataString Message received
	 * @return {object}            Object to be used for pub/sub
	 */
	function parseMessage(dataString) {
		/*eslint no-empty: 0*/
		var data;
		if (typeof dataString !== 'string') {
			return;
		}

		try {
			data = JSON.parse(dataString);
		} catch (ex) {}

		if (!verify(data)) {
			return;
		}

		if (typeof data.error === 'object') {
			data.error = buildErrorObject(data.error);
		} else {
			data.error = undefined;
		}
		return data;
	}

	if (typeof window.addEventListener === 'function') {
		window.addEventListener(
			'message',
			function(e) {
				var data = parseMessage(e.data);
				if (!data || !data._axeuuid) {
					return;
				}

				var uuid = data.uuid;

				/**
				 * NOTE: messages from other contexts (frames) in response
				 * to a message should not contain the same axe._uuid. We
				 * ignore these messages to prevent rogue postMessage
				 * handlers reflecting our messages.
				 * @see https://github.com/dequelabs/axe-core/issues/1754
				 */
				var axeRespondables = axe._cache.get('axeRespondables') || {};
				if (axeRespondables[uuid] && data._axeuuid === axe._uuid) {
					return;
				}

				var keepalive = data._keepalive;
				var callback = messages[uuid];

				if (callback) {
					var result = data.error || data.message;
					var responder = createResponder(e.source, data.topic, uuid);
					callback(result, keepalive, responder);

					if (!keepalive) {
						delete messages[uuid];
					}
				}

				if (!data.error) {
					try {
						publish(e.source, data, keepalive);
					} catch (err) {
						post(e.source, null, err, uuid, false);
					}
				}
			},
			false
		);
	}

	exports.respondable = respondable;
})(utils);
