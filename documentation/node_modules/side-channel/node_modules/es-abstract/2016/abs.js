'use strict';

var GetIntrinsic = require('../GetIntrinsic');

var $abs = GetIntrinsic('%Math.abs%');

// http://www.ecma-international.org/ecma-262/5.1/#sec-5.2

module.exports = function abs(x) {
	return $abs(x);
};
