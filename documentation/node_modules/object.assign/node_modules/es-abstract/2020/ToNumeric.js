'use strict';

var GetIntrinsic = require('../GetIntrinsic');

var $Number = GetIntrinsic('%Number%');

var isPrimitive = require('../helpers/isPrimitive');

var ToPrimitive = require('./ToPrimitive');
var ToNumber = require('./ToNumber');
var Type = require('./Type');

// https://www.ecma-international.org/ecma-262/6.0/#sec-tonumber

module.exports = function ToNumeric(argument) {
	var primValue = isPrimitive(argument) ? argument : ToPrimitive(argument, $Number);
	if (Type(primValue) === 'BigInt') {
		return primValue;
	}
	return ToNumber(primValue);
};
