'use strict';

// https://tc39.es/ecma262/2020/#sec-isbigintelementtype

module.exports = function IsBigIntElementType(type) {
	return type === 'BigUint64' || type === 'BigInt64';
};
