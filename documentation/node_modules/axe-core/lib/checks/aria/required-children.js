const requiredOwned = axe.commons.aria.requiredOwned;
const implicitNodes = axe.commons.aria.implicitNodes;
const matchesSelector = axe.utils.matchesSelector;
const idrefs = axe.commons.dom.idrefs;
const hasContentVirtual = axe.commons.dom.hasContentVirtual;
const reviewEmpty =
	options && Array.isArray(options.reviewEmpty) ? options.reviewEmpty : [];

function owns(node, virtualTree, role, ariaOwned) {
	if (node === null) {
		return false;
	}
	const implicit = implicitNodes(role);
	let selector = ['[role="' + role + '"]'];

	if (implicit) {
		selector = selector.concat(
			implicit.map(implicitSelector => implicitSelector + ':not([role])')
		);
	}

	selector = selector.join(',');
	return ariaOwned
		? matchesSelector(node, selector) ||
				!!axe.utils.querySelectorAll(virtualTree, selector)[0]
		: !!axe.utils.querySelectorAll(virtualTree, selector)[0];
}

function ariaOwns(nodes, role) {
	for (let index = 0; index < nodes.length; index++) {
		const node = nodes[index];
		if (node === null) {
			continue;
		}
		const virtualTree = axe.utils.getNodeFromTree(node);
		if (owns(node, virtualTree, role, true)) {
			return true;
		}
	}
	return false;
}

function missingRequiredChildren(node, childRoles, all, role) {
	const missing = [],
		ownedElements = idrefs(node, 'aria-owns');

	for (let index = 0; index < childRoles.length; index++) {
		const childRole = childRoles[index];
		if (
			owns(node, virtualNode, childRole) ||
			ariaOwns(ownedElements, childRole)
		) {
			if (!all) {
				return null;
			}
		} else {
			if (all) {
				missing.push(childRole);
			}
		}
	}

	// combobox exceptions
	if (role === 'combobox') {
		// remove 'textbox' from missing roles if combobox is a native text-type input or owns a 'searchbox'
		const textboxIndex = missing.indexOf('textbox');
		const textTypeInputs = ['text', 'search', 'email', 'url', 'tel'];
		if (
			(textboxIndex >= 0 &&
				node.nodeName.toUpperCase() === 'INPUT' &&
				textTypeInputs.includes(node.type)) ||
			owns(node, virtualNode, 'searchbox') ||
			ariaOwns(ownedElements, 'searchbox')
		) {
			missing.splice(textboxIndex, 1);
		}

		const expandedChildRoles = ['listbox', 'tree', 'grid', 'dialog'];
		const expandedValue = node.getAttribute('aria-expanded');
		const expanded = expandedValue && expandedValue !== 'false';
		const popupRole = (
			node.getAttribute('aria-haspopup') || 'listbox'
		).toLowerCase();

		for (let index = 0; index < expandedChildRoles.length; index++) {
			const expandedChildRole = expandedChildRoles[index];
			// keep the specified popup type required if expanded
			if (expanded && expandedChildRole === popupRole) {
				continue;
			}

			// remove 'listbox' and company from missing roles if combobox is collapsed
			const missingIndex = missing.indexOf(expandedChildRole);
			if (missingIndex >= 0) {
				missing.splice(missingIndex, 1);
			}
		}
	}

	if (missing.length) {
		return missing;
	}
	if (!all && childRoles.length) {
		return childRoles;
	}
	return null;
}

function hasDecendantWithRole(node) {
	return (
		node.children &&
		node.children.some(child => {
			const role = axe.commons.aria.getRole(child);
			return (
				!['presentation', 'none', null].includes(role) ||
				hasDecendantWithRole(child)
			);
		})
	);
}

const role = node.getAttribute('role');
const required = requiredOwned(role);

if (!required) {
	return true;
}

let all = false;
let childRoles = required.one;
if (!childRoles) {
	all = true;
	childRoles = required.all;
}

const missing = missingRequiredChildren(node, childRoles, all, role);

if (!missing) {
	return true;
}

this.data(missing);

// Only review empty nodes when a node is both empty and does not have an aria-owns relationship
if (
	reviewEmpty.includes(role) &&
	!hasContentVirtual(virtualNode, false, true) &&
	!hasDecendantWithRole(virtualNode) &&
	idrefs(node, 'aria-owns').length === 0
) {
	return undefined;
} else {
	return false;
}
