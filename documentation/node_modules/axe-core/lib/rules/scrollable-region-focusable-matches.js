/**
 * Note:
 * `excludeHidden=true` for this rule, thus considering only elements in the accessibility tree.
 */
const { querySelectorAll } = axe.utils;
const { hasContentVirtual } = axe.commons.dom;

/**
 * if not scrollable -> `return`
 */
if (!!axe.utils.getScroll(node, 13) === false) {
	return false;
}

/**
 * check if node has visible contents
 */
const nodeAndDescendents = querySelectorAll(virtualNode, '*');
const hasVisibleChildren = nodeAndDescendents.some(elm =>
	hasContentVirtual(
		elm,
		true, // noRecursion
		true // ignoreAria
	)
);
if (!hasVisibleChildren) {
	return false;
}

return true;
