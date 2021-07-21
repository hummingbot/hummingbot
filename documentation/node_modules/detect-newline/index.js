'use strict';
module.exports = function (str) {
	if (typeof str !== 'string') {
		throw new TypeError('Expected a string');
	}

	var newlines = (str.match(/(?:\r?\n)/g) || []);
	var crlf = newlines.filter(function (el) { return el === '\r\n'; }).length;
	var lf = newlines.length - crlf;

	return crlf > lf ? '\r\n' : '\n';
};
