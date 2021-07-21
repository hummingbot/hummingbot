/* global aria, axe */

/**
 * Check if a given role is valid
 * @method isValidRole
 * @memberof axe.commons.aria
 * @instance
 * @param {String} role The role to check
 * @param {Object} options Use `allowAbstract` if you want abstracts, and `flagUnsupported: true` to report unsupported roles
 * @return {Boolean}
 */
aria.isValidRole = function(
	role,
	{ allowAbstract, flagUnsupported = false } = {}
) {
	const roleDefinition = aria.lookupTable.role[role];
	const isRoleUnsupported = roleDefinition ? roleDefinition.unsupported : false;
	if (!roleDefinition || (flagUnsupported && isRoleUnsupported)) {
		return false;
	}
	return allowAbstract ? true : roleDefinition.type !== 'abstract';
};

/**
 * Get the roles that get name from the element's contents
 * @method getRolesWithNameFromContents
 * @memberof axe.commons.aria
 * @instance
 * @return {Array} Array of roles that match the type
 */
aria.getRolesWithNameFromContents = function() {
	return Object.keys(aria.lookupTable.role).filter(function(r) {
		return (
			aria.lookupTable.role[r].nameFrom &&
			aria.lookupTable.role[r].nameFrom.indexOf('contents') !== -1
		);
	});
};

/**
 * Get the roles that have a certain "type"
 * @method getRolesByType
 * @memberof axe.commons.aria
 * @instance
 * @param {String} roleType The roletype to check
 * @return {Array} Array of roles that match the type
 */
aria.getRolesByType = function(roleType) {
	return Object.keys(aria.lookupTable.role).filter(function(r) {
		return aria.lookupTable.role[r].type === roleType;
	});
};

/**
 * Get the "type" of role; either widget, composite, abstract, landmark or `null`
 * @method getRoleType
 * @memberof axe.commons.aria
 * @instance
 * @param {String} role The role to check
 * @return {Mixed} String if a matching role and its type are found, otherwise `null`
 */
aria.getRoleType = function(role) {
	var r = aria.lookupTable.role[role];
	return (r && r.type) || null;
};

/**
 * Get the required owned (children) roles for a given role
 * @method requiredOwned
 * @memberof axe.commons.aria
 * @instance
 * @param {String} role The role to check
 * @return {Mixed} Either an Array of required owned elements or `null` if there are none
 */
aria.requiredOwned = function(role) {
	'use strict';
	var owned = null,
		roles = aria.lookupTable.role[role];

	if (roles) {
		owned = axe.utils.clone(roles.owned);
	}
	return owned;
};

/**
 * Get the required context (parent) roles for a given role
 * @method requiredContext
 * @memberof axe.commons.aria
 * @instance
 * @param {String} role The role to check
 * @return {Mixed} Either an Array of required context elements or `null` if there are none
 */
aria.requiredContext = function(role) {
	'use strict';
	var context = null,
		roles = aria.lookupTable.role[role];

	if (roles) {
		context = axe.utils.clone(roles.context);
	}
	return context;
};

/**
 * Get a list of CSS selectors of nodes that have an implicit role
 * @method implicitNodes
 * @memberof axe.commons.aria
 * @instance
 * @param {String} role The role to check
 * @return {Mixed} Either an Array of CSS selectors or `null` if there are none
 */
aria.implicitNodes = function(role) {
	'use strict';

	var implicit = null,
		roles = aria.lookupTable.role[role];

	if (roles && roles.implicit) {
		implicit = axe.utils.clone(roles.implicit);
	}
	return implicit;
};

/**
 * Get the implicit role for a given node
 * @method implicitRole
 * @memberof axe.commons.aria
 * @instance
 * @param {HTMLElement} node The node to test
 * @return {Mixed} Either the role or `null` if there is none
 */
aria.implicitRole = function(node) {
	'use strict';

	/*
	 * Filter function to reduce a list of roles to a valid list of roles for a nodetype
	 */
	var isValidImplicitRole = function(set, role) {
		var validForNodeType = function(implicitNodeTypeSelector) {
			return axe.utils.matchesSelector(node, implicitNodeTypeSelector);
		};

		if (role.implicit && role.implicit.some(validForNodeType)) {
			set.push(role.name);
		}

		return set;
	};

	/*
	 * Score a set of roles and aria-attributes by its optimal score
	 * E.g. [{score: 2, name: button}, {score: 1, name: main}]
	 */
	var sortRolesByOptimalAriaContext = function(roles, ariaAttributes) {
		var getScore = function(role) {
			var allowedAriaAttributes = aria.allowedAttr(role);
			return allowedAriaAttributes.reduce(function(score, attribute) {
				return score + (ariaAttributes.indexOf(attribute) > -1 ? 1 : 0);
			}, 0);
		};

		var scored = roles.map(function(role) {
			return { score: getScore(role), name: role };
		});

		var sorted = scored.sort(function(scoredRoleA, scoredRoleB) {
			return scoredRoleB.score - scoredRoleA.score;
		});

		return sorted.map(function(sortedRole) {
			return sortedRole.name;
		});
	};

	/*
	 * Create a list of { name / implicit } role mappings to filter on
	 */
	var roles = Object.keys(aria.lookupTable.role).map(function(role) {
		var lookup = aria.lookupTable.role[role];
		return { name: role, implicit: lookup && lookup.implicit };
	});

	/* Build a list of valid implicit roles for this node */
	var availableImplicitRoles = roles.reduce(isValidImplicitRole, []);

	if (!availableImplicitRoles.length) {
		return null;
	}

	var nodeAttributes = axe.utils.getNodeAttributes(node);
	var ariaAttributes = [];

	/* Get all aria-attributes defined for this node */
	/* Should be a helper function somewhere */
	for (var i = 0, j = nodeAttributes.length; i < j; i++) {
		var attr = nodeAttributes[i];
		if (attr.name.match(/^aria-/)) {
			ariaAttributes.push(attr.name);
		}
	}

	/* Sort roles by highest score, return the first */
	return sortRolesByOptimalAriaContext(
		availableImplicitRoles,
		ariaAttributes
	).shift();
};
