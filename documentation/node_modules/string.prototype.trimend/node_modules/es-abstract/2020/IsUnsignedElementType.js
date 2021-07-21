'use strict';

// https://tc39.es/ecma262/2020/#sec-isunsignedelementtype

module.exports = function IsUnsignedElementType(type) {
	return type === 'Uint8'
        || type === 'Uint8C'
        || type === 'Uint16'
        || type === 'Uint32'
        || type === 'BigUint64';
};
