function getSelector(role) {
	var impliedNative = axe.commons.aria.implicitNodes(role) || [];
	return impliedNative.concat('[role="' + role + '"]').join(',');
}

function getMissingContext(virtualNode, requiredContext, includeElement) {
	var index,
		length,
		role = virtualNode.actualNode.getAttribute('role'),
		missing = [];

	if (!requiredContext) {
		requiredContext = axe.commons.aria.requiredContext(role);
	}

	if (!requiredContext) {
		return null;
	}

	for (index = 0, length = requiredContext.length; index < length; index++) {
		if (
			includeElement &&
			axe.utils.matchesSelector(
				virtualNode.actualNode,
				getSelector(requiredContext[index])
			)
		) {
			return null;
		}
		if (
			axe.commons.dom.findUpVirtual(
				virtualNode,
				getSelector(requiredContext[index])
			)
		) {
			//if one matches, it passes
			return null;
		} else {
			missing.push(requiredContext[index]);
		}
	}

	return missing;
}

function getAriaOwners(element) {
	var owners = [],
		o = null;

	while (element) {
		if (element.getAttribute('id')) {
			const id = axe.utils.escapeSelector(element.getAttribute('id'));
			let doc = axe.commons.dom.getRootNode(element);
			o = doc.querySelector(`[aria-owns~=${id}]`);
			if (o) {
				owners.push(o);
			}
		}
		element = element.parentElement;
	}

	return owners.length ? owners : null;
}

var missingParents = getMissingContext(virtualNode);

if (!missingParents) {
	return true;
}

var owners = getAriaOwners(node);

if (owners) {
	for (var i = 0, l = owners.length; i < l; i++) {
		missingParents = getMissingContext(
			axe.utils.getNodeFromTree(owners[i]),
			missingParents,
			true
		);
		if (!missingParents) {
			return true;
		}
	}
}

this.data(missingParents);
return false;
