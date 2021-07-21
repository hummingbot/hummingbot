/**
 * set the scroll position of an element
 */
function setScroll(elm, top, left) {
	if (elm === window) {
		return elm.scroll(left, top);
	} else {
		elm.scrollTop = top;
		elm.scrollLeft = left;
	}
}

/**
 * Create an array scroll positions from descending elements
 */
function getElmScrollRecursive(root) {
	// Need to also get .childNodes since SVGs in IE don't have .children.
	return Array.from(root.children || root.childNodes || []).reduce(
		(scrolls, elm) => {
			const scroll = axe.utils.getScroll(elm);
			if (scroll) {
				scrolls.push(scroll);
			}
			return scrolls.concat(getElmScrollRecursive(elm));
		},
		[]
	);
}

/**
 * Get the scroll position of all scrollable elements in a page
 */
axe.utils.getScrollState = function getScrollState(win = window) {
	const root = win.document.documentElement;
	const windowScroll = [
		win.pageXOffset !== undefined
			? {
					elm: win,
					top: win.pageYOffset,
					left: win.pageXOffset
			  }
			: {
					elm: root,
					top: root.scrollTop,
					left: root.scrollLeft
			  }
	];

	return windowScroll.concat(getElmScrollRecursive(document.body));
};

/**
 * set the scroll position of all items in the scrollState array
 */
axe.utils.setScrollState = function setScrollState(scrollState) {
	scrollState.forEach(({ elm, top, left }) => setScroll(elm, top, left));
};
