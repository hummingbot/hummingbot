var chalk = require('chalk');

function print(msg) {
	console.error(chalk.red(msg));
}

var handlers = {
	MISSING_INPUT_OPTION: () => {
		print('You must specify an --input (-i) option');
	},

	MISSING_OUTPUT_DIR: () => {
		print(
			'You must specify an --output (-o) option when compiling a directory of files'
		);
	},

	MISSING_OUTPUT_FILE: () => {
		print(
			'You must specify an --output (-o) option when creating a file with a sourcemap'
		);
	},

	ONE_AT_A_TIME: () => {
		print('Bublé can only compile one file/directory at a time');
	},

	DUPLICATE_IMPORT_OPTIONS: () => {
		print('use --input, or pass input path as argument – not both');
	},

	BAD_TARGET: () => {
		print('illegal --target option');
	}
};

module.exports = function handleError(err) {
	var handler;

	if ((handler = handlers[err && err.code])) {
		handler(err);
	} else {
		if (err.snippet) print('---\n' + err.snippet);
		print(err.message || err);

		if (err.stack) {
			console.error(chalk.grey(err.stack));
		}
	}

	console.error(
		'Type ' +
			chalk.cyan('buble --help') +
			' for help, or visit https://buble.surge.sh/guide/'
	);

	process.exit(1);
};
