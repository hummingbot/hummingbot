const tabIndex = parseInt(node.getAttribute('tabindex'), 10);

// an invalid tabindex will either return 0 or -1 (based on the element) so
// will never be above 0
// @see https://www.w3.org/TR/html51/editing.html#the-tabindex-attribute
return isNaN(tabIndex) ? true : tabIndex <= 0;
