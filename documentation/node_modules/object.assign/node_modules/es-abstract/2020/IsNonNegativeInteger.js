'use strict';

var IsInteger = require('./IsInteger');

// https://tc39.es/ecma262/2020/#sec-isnonnegativeinteger

module.exports = function IsNonNegativeInteger(argument) {
	return !!IsInteger(argument) && argument >= 0;
};
