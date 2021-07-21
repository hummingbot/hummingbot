#!/usr/bin/env node
'use strict';
var stdin = require('get-stdin');
var argv = require('minimist')(process.argv.slice(2));
var pkg = require('./package.json');
var detectNewline = require('./');
var input = argv._[0];

function help() {
	console.log([
		'',
		'  ' + pkg.description,
		'',
		'  Usage',
		'    detect-newline <string>',
		'    cat unicorn.txt | detect-newline',
		'',
		'  Example',
		'    detect-newline "$(printf \'Unicorns\\nRainbows\')"',
		'    \\n'
	].join('\n'));
}

function init(data) {
	process.stdout.write(detectNewline(data));
}

if (argv.help) {
	help();
	return;
}

if (argv.version) {
	console.log(pkg.version);
	return;
}

if (process.stdin.isTTY) {
	if (!input) {
		help();
		return;
	}

	init(input);
} else {
	stdin(init);
}
