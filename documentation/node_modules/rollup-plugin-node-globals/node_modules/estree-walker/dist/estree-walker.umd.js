(function (global, factory) {
	typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
	typeof define === 'function' && define.amd ? define(['exports'], factory) :
	(factory((global.estreeWalker = {})));
}(this, (function (exports) { 'use strict';

function walk ( ast, ref) {
	var enter = ref.enter;
	var leave = ref.leave;

	visit( ast, null, enter, leave );
}

var shouldSkip = false;
var context = { skip: function () { return shouldSkip = true; } };

var childKeys = {};

var toString = Object.prototype.toString;

function isArray ( thing ) {
	return toString.call( thing ) === '[object Array]';
}

function visit ( node, parent, enter, leave, prop, index ) {
	if ( !node ) { return; }

	if ( enter ) {
		var _shouldSkip = shouldSkip;
		shouldSkip = false;
		enter.call( context, node, parent, prop, index );
		var skipped = shouldSkip;
		shouldSkip = _shouldSkip;

		if ( skipped ) { return; }
	}

	var keys = childKeys[ node.type ] || (
		childKeys[ node.type ] = Object.keys( node ).filter( function (key) { return typeof node[ key ] === 'object'; } )
	);

	for ( var i = 0; i < keys.length; i += 1 ) {
		var key = keys[i];
		var value = node[ key ];

		if ( isArray( value ) ) {
			for ( var j = 0; j < value.length; j += 1 ) {
				visit( value[j], node, enter, leave, key, j );
			}
		}

		else if ( value && value.type ) {
			visit( value, node, enter, leave, key, null );
		}
	}

	if ( leave ) {
		leave( node, parent, prop, index );
	}
}

exports.walk = walk;
exports.childKeys = childKeys;

Object.defineProperty(exports, '__esModule', { value: true });

})));
//# sourceMappingURL=estree-walker.umd.js.map
