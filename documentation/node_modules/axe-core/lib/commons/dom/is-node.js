/* global dom */
/**
 * Determines if element is an instance of Node
 * @method isNode
 * @memberof axe.commons.dom
 * @instance
 * @param  {Element} element
 * @return {Boolean}
 */
dom.isNode = function(element) {
	'use strict';
	return element instanceof Node;
};
