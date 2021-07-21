/* global dom */

/**
 * Determines if a document node is HTML 5
 * @method isHTML5
 * @memberof axe.commons.dom
 * @instance
 * @param {Node} doc
 * @return {Boolean}
 */
dom.isHTML5 = function(doc) {
	var node = doc.doctype;
	if (node === null) {
		return false;
	}
	return node.name === 'html' && !node.publicId && !node.systemId;
};
