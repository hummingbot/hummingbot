const { dom, aria } = axe.commons;

let hasNonEmptyTextNode = false;
let atLeastOneListitem = false;
let isEmpty = true;
let badNodes = [];
let badRoleNodes = [];
let badRoles = [];

virtualNode.children.forEach(vNode => {
	const { actualNode } = vNode;

	if (actualNode.nodeType === 3 && actualNode.nodeValue.trim() !== '') {
		hasNonEmptyTextNode = true;
		return;
	}

	if (actualNode.nodeType !== 1 || !dom.isVisible(actualNode, true, false)) {
		return;
	}

	isEmpty = false;
	const isLi = actualNode.nodeName.toUpperCase() === 'LI';
	const role = aria.getRole(vNode);
	const isListItemRole = role === 'listitem';

	if (!isLi && !isListItemRole) {
		badNodes.push(actualNode);
	}

	if (isLi && !isListItemRole) {
		badRoleNodes.push(actualNode);

		if (!badRoles.includes(role)) {
			badRoles.push(role);
		}
	}

	if (isListItemRole) {
		atLeastOneListitem = true;
	}
});

if (hasNonEmptyTextNode || badNodes.length) {
	this.relatedNodes(badNodes);
	return true;
}

if (isEmpty || atLeastOneListitem) {
	return false;
}

this.relatedNodes(badRoleNodes);
this.data({
	messageKey: 'roleNotValid',
	roles: badRoles.join(', ')
});
return true;
