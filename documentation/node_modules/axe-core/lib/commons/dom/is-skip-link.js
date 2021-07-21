/* global dom */

// test for hrefs that start with # or /# (for angular)
const isInternalLinkRegex = /^\/?#[^/!]/;

/**
 * Determines if element is a skip link
 * @method isSkipLink
 * @memberof axe.commons.dom
 * @instance
 * @param  {Element} element
 * @return {Boolean}
 */
dom.isSkipLink = function(element) {
	if (!isInternalLinkRegex.test(element.getAttribute('href'))) {
		return false;
	}

	let firstPageLink;
	if (typeof axe._cache.get('firstPageLink') !== 'undefined') {
		firstPageLink = axe._cache.get('firstPageLink');
	} else {
		// define a skip link as any anchor element whose href starts with `#...`
		// and which precedes the first anchor element whose href doesn't start
		// with  `#...` (that is, a link to a page)
		firstPageLink = axe.utils.querySelectorAll(
			axe._tree,
			'a:not([href^="#"]):not([href^="/#"]):not([href^="javascript"])'
		)[0];

		// null will signify no first page link
		axe._cache.set('firstPageLink', firstPageLink || null);
	}

	// if there are no page links then all all links will need to be
	// considered as skip links
	if (!firstPageLink) {
		return true;
	}

	return (
		element.compareDocumentPosition(firstPageLink.actualNode) ===
		element.DOCUMENT_POSITION_FOLLOWING
	);
};
