/**
 * Determines if a document node is XHTML
 * @method isXHTML
 * @memberof axe.utils
 * @param {Node} doc a document node
 * @return {Boolean}
 */
axe.utils.isXHTML = function(doc) {
	'use strict';
	if (!doc.createElement) {
		return false;
	}
	return doc.createElement('A').localName === 'A';
};
