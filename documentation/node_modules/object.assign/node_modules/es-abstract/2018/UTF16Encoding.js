'use strict';

var GetIntrinsic = require('../GetIntrinsic');

var $TypeError = GetIntrinsic('%TypeError%');
var $fromCharCode = GetIntrinsic('%String.fromCharCode%');

var floor = require('./floor');
var modulo = require('./modulo');

// https://ecma-international.org/ecma-262/7.0/#sec-utf16encoding

module.exports = function UTF16Encoding(cp) {
	if (typeof cp !== 'number' || cp < 0 || cp > 0x10FFFF) {
		throw new $TypeError('Assertion failed: `cp` must be >= 0 and <= 0x10FFFF');
	}
	if (cp <= 65535) {
		return cp;
	}
	var cu1 = floor((cp - 65536) / 1024) + 0xD800;
	var cu2 = modulo(cp - 65536, 1024) + 0xDC00;
	return $fromCharCode(cu1) + $fromCharCode(cu2);
};
