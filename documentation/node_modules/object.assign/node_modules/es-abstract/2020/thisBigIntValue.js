'use strict';

var GetIntrinsic = require('../GetIntrinsic');
var callBound = require('../helpers/callBound');

var $TypeError = GetIntrinsic('%TypeError%');
var $bigIntValueOf = callBound('BigInt.prototype.valueOf', true);

var Type = require('./Type');

// https://tc39.es/ecma262/2020/#sec-thisbigintvalue

module.exports = function thisBigIntValue(value) {
	var type = Type(value);
	if (type === 'BigInt') {
		return value;
	}
	if (!$bigIntValueOf) {
		throw new $TypeError('BigInt is not supported');
	}
	return $bigIntValueOf(value);
};
