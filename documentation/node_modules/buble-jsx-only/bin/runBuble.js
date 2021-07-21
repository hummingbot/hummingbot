var fs = require('fs');
var path = require('path');
var buble = require('..');
var handleError = require('./handleError.js');
var EOL = require('os').EOL;

function compile(from, to, command, options) {
	try {
		var stats = fs.statSync(from);
		if (stats.isDirectory()) {
			compileDir(from, to, command, options);
		} else {
			compileFile(from, to, command, options);
		}
	} catch (err) {
		handleError(err);
	}
}

function compileDir(from, to, command, options) {
	if (!command.output) handleError({ code: 'MISSING_OUTPUT_DIR' });

	try {
		fs.mkdirSync(to);
	} catch (e) {
		if (e.code !== 'EEXIST') throw e;
	}

	fs.readdirSync(from).forEach(function(file) {
		compile(path.resolve(from, file), path.resolve(to, file), command, options);
	});
}

function compileFile(from, to, command, options) {
	var ext = path.extname(from);

	if (ext !== '.js' && ext !== '.jsm' && ext !== '.es6' && ext !== '.jsx')
		return;

	if (to) {
		var extTo = path.extname(to);
		to = to.slice(0, -extTo.length) + '.js';
	}

	var source = fs.readFileSync(from, 'utf-8');
	var result = buble.transform(source, {
		target: options.target,
		transforms: options.transforms,
		source: from,
		file: to,
		jsx: options.jsx,
		objectAssign: options.objectAssign,
		namedFunctionExpressions: options.namedFunctionExpressions
	});

	write(result, to, command);
}

function write(result, to, command) {
	if (command.sourcemap === 'inline') {
		result.code += EOL + '//# sourceMappingURL=' + result.map.toUrl();
	} else if (command.sourcemap) {
		if (!to) {
			handleError({ code: 'MISSING_OUTPUT_FILE' });
		}

		result.code += EOL + '//# sourceMappingURL=' + path.basename(to) + '.map';
		fs.writeFileSync(to + '.map', result.map.toString());
	}

	if (to) {
		fs.writeFileSync(to, result.code);
	} else {
		console.log(result.code);
	}
}

module.exports = function(command) {
	if (command._.length > 1) {
		handleError({ code: 'ONE_AT_A_TIME' });
	}

	if (command._.length === 1) {
		if (command.input) {
			handleError({ code: 'DUPLICATE_IMPORT_OPTIONS' });
		}

		command.input = command._[0];
	}

	var options = {
		target: {},
		transforms: {},
		jsx: command.jsx,
		objectAssign: command.objectAssign,
		namedFunctionExpressions: command['named-function-expr'] !== false
	};

	if (command.target) {
		if (!/^(?:(\w+):([\d.]+),)*(\w+):([\d.]+)$/.test(command.target)) {
			handleError({ code: 'BAD_TARGET' });
		}

		command.target
			.split(',')
			.map(function(target) {
				return target.split(':');
			})
			.forEach(function(pair) {
				options.target[pair[0]] = pair[1];
			});
	}

	if (command.yes) {
		command.yes.split(',').forEach(function(transform) {
			options.transforms[transform] = true;
		});
	}

	if (command.no) {
		command.no.split(',').forEach(function(transform) {
			options.transforms[transform] = false;
		});
	}

	if (command.input) {
		compile(command.input, command.output, command, options);
	} else {
		process.stdin.resume();
		process.stdin.setEncoding('utf8');

		var source = '';

		process.stdin.on('data', function(chunk) {
			source += chunk;
		});

		process.stdin.on('end', function() {
			options.source = command.input = 'stdin';
			options.file = command.output;
			try {
				var result = buble.transform(source, options);
				write(result, command.output, command);
			} catch (err) {
				handleError(err);
			}
		});
	}
};
