'use strict';
const util = require('util');
const onExit = require('signal-exit');
const currentlyUnhandled = require('currently-unhandled');

let installed = false;

const loudRejection = (log = console.error) => {
	if (installed) {
		return;
	}

	installed = true;

	const listUnhandled = currentlyUnhandled();

	onExit(() => {
		const unhandledRejections = listUnhandled();

		if (unhandledRejections.length > 0) {
			for (const unhandledRejection of unhandledRejections) {
				let error = unhandledRejection.reason;

				if (!(error instanceof Error)) {
					error = new Error(`Promise rejected with value: ${util.inspect(error)}`);
				}

				log(error.stack);
			}

			process.exitCode = 1;
		}
	});
};

module.exports = loudRejection;
// TODO: remove this in the next major version
module.exports.default = loudRejection;
