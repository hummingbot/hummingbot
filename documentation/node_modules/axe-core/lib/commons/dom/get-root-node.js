/* global dom */

/**
 * Return the document or document fragment (shadow DOM)
 * @method getRootNode
 * @memberof axe.commons.dom
 * @instance
 * @param {Element} node
 * @returns {DocumentFragment|Document}
 * @deprecated use axe.utils.getRootNode
 */
dom.getRootNode = axe.utils.getRootNode;
