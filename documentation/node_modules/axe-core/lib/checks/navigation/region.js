const { dom, aria } = axe.commons;
const landmarkRoles = aria.getRolesByType('landmark');
const implicitAriaLiveRoles = ['alert', 'log', 'status'];

let regionlessNodes = axe._cache.get('regionlessNodes');
if (regionlessNodes) {
	return !regionlessNodes.includes(virtualNode);
}

// Create a list of nodeNames that have a landmark as an implicit role
const implicitLandmarks = landmarkRoles
	.reduce((arr, role) => arr.concat(aria.implicitNodes(role)), [])
	.filter(r => r !== null);

// Check if the current element is a landmark
function isRegion(virtualNode) {
	const node = virtualNode.actualNode;
	const explicitRole = axe.commons.aria.getRole(node, { noImplicit: true });
	const ariaLive = (node.getAttribute('aria-live') || '').toLowerCase().trim();

	// Ignore content inside of aria-live
	if (
		['assertive', 'polite'].includes(ariaLive) ||
		implicitAriaLiveRoles.includes(explicitRole)
	) {
		return true;
	}

	if (explicitRole) {
		return explicitRole === 'dialog' || landmarkRoles.includes(explicitRole);
	}

	// Check if the node matches any of the CSS selectors of implicit landmarks
	return implicitLandmarks.some(implicitSelector => {
		let matches = axe.utils.matchesSelector(node, implicitSelector);
		if (node.nodeName.toUpperCase() === 'FORM') {
			let titleAttr = node.getAttribute('title');
			let title =
				titleAttr && titleAttr.trim() !== ''
					? axe.commons.text.sanitize(titleAttr)
					: null;
			return matches && (!!aria.labelVirtual(virtualNode) || !!title);
		}
		return matches;
	});
}

/**
 * Find all visible elements not wrapped inside a landmark or skiplink
 */
function findRegionlessElms(virtualNode) {
	const node = virtualNode.actualNode;
	// End recursion if the element is a landmark, skiplink, or hidden content
	if (
		isRegion(virtualNode) ||
		(dom.isSkipLink(virtualNode.actualNode) &&
			dom.getElementByReference(virtualNode.actualNode, 'href')) ||
		!dom.isVisible(node, true)
	) {
		// Mark each parent node as having region descendant
		let vNode = virtualNode;
		while (vNode) {
			vNode._hasRegionDescendant = true;
			vNode = vNode.parent;
		}

		return [];

		// Return the node is a content element. Ignore any direct text children
		// of body so we don't report body as being outside of a landmark.
		// @see https://github.com/dequelabs/axe-core/issues/2049
	} else if (
		node !== document.body &&
		dom.hasContent(node, /* noRecursion: */ true)
	) {
		return [virtualNode];

		// Recursively look at all child elements
	} else {
		return virtualNode.children
			.filter(({ actualNode }) => actualNode.nodeType === 1)
			.map(findRegionlessElms)
			.reduce((a, b) => a.concat(b), []); // flatten the results
	}
}

regionlessNodes = findRegionlessElms(axe._tree[0])
	// Find first parent marked as having region descendant (or body) and
	// return the node right before it as the "outer" element
	.map(vNode => {
		while (
			vNode.parent &&
			!vNode.parent._hasRegionDescendant &&
			vNode.parent.actualNode !== document.body
		) {
			vNode = vNode.parent;
		}

		return vNode;
	})
	// Remove duplicate containers
	.filter((vNode, index, array) => {
		return array.indexOf(vNode) === index;
	});
axe._cache.set('regionlessNodes', regionlessNodes);

return !regionlessNodes.includes(virtualNode);
