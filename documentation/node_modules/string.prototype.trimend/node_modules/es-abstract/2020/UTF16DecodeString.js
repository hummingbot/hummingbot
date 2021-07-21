'use strict';

var GetIntrinsic = require('../GetIntrinsic');

var $TypeError = GetIntrinsic('%TypeError%');

var callBound = require('../helpers/callBound');

var $push = callBound('Array.prototype.push');

var CodePointAt = require('./CodePointAt');
var Type = require('./Type');

// https://tc39.es/ecma262/2020/#sec-utf16decodestring

module.exports = function UTF16DecodeString(string) {
	if (Type(string) !== 'String') {
		throw new $TypeError('Assertion failed: `string` must be a String');
	}
	var codePoints = [];
	var size = string.length;
	var position = 0;
	while (position < size) {
		var cp = CodePointAt(string, position);
		$push(codePoints, cp['[[CodePoint]]']);
		position += cp['[[CodeUnitCount]]'];
	}
	return codePoints;
};
