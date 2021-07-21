function createLocalVariables(vNodes, anyLevel, thisLevel, parentShadowId) {
	let retVal = {
		vNodes: vNodes.slice(),
		anyLevel: anyLevel,
		thisLevel: thisLevel,
		parentShadowId: parentShadowId
	};
	retVal.vNodes.reverse();
	return retVal;
}

function matchExpressions(domTree, expressions, filter) {
	let stack = [];
	let vNodes = Array.isArray(domTree) ? domTree : [domTree];
	let currentLevel = createLocalVariables(
		vNodes,
		expressions,
		[],
		domTree[0].shadowId
	);
	let result = [];

	while (currentLevel.vNodes.length) {
		let vNode = currentLevel.vNodes.pop();
		let childOnly = []; // we will add hierarchical '>' selectors here
		let childAny = [];
		let combined = currentLevel.anyLevel.slice().concat(currentLevel.thisLevel);
		let added = false;
		// see if node matches
		for (let i = 0; i < combined.length; i++) {
			let exp = combined[i];
			if (
				(!exp[0].id || vNode.shadowId === currentLevel.parentShadowId) &&
				axe.utils.matchesExpression(vNode, exp[0])
			) {
				if (exp.length === 1) {
					if (!added && (!filter || filter(vNode))) {
						result.push(vNode);
						added = true;
					}
				} else {
					let rest = exp.slice(1);
					if ([' ', '>'].includes(rest[0].combinator) === false) {
						throw new Error(
							'axe.utils.querySelectorAll does not support the combinator: ' +
								exp[1].combinator
						);
					}
					if (rest[0].combinator === '>') {
						// add the rest to the childOnly array
						childOnly.push(rest);
					} else {
						// add the rest to the childAny array
						childAny.push(rest);
					}
				}
			}
			if (
				(!exp[0].id || vNode.shadowId === currentLevel.parentShadowId) &&
				currentLevel.anyLevel.includes(exp)
			) {
				childAny.push(exp);
			}
		}

		if (vNode.children && vNode.children.length) {
			stack.push(currentLevel);
			currentLevel = createLocalVariables(
				vNode.children,
				childAny,
				childOnly,
				vNode.shadowId
			);
		}
		// check for "return"
		while (!currentLevel.vNodes.length && stack.length) {
			currentLevel = stack.pop();
		}
	}
	return result;
}

/**
 * querySelectorAll implementation that operates on the flattened tree (supports shadow DOM)
 * @method querySelectorAll
 * @memberof axe.utils
 * @param	{NodeList} domTree flattened tree collection to search
 * @param	{String} selector String containing one or more CSS selectors separated by commas
 * @return {NodeList} Elements matched by any of the selectors
 */
axe.utils.querySelectorAll = function(domTree, selector) {
	return axe.utils.querySelectorAllFilter(domTree, selector);
};

/**
 * querySelectorAllFilter implements querySelectorAll on the virtual DOM with
 * ability to filter the returned nodes using an optional supplied filter function
 *
 * @method querySelectorAllFilter
 * @memberof axe.utils
 * @param	{NodeList} domTree flattened tree collection to search
 * @param	{String} selector String containing one or more CSS selectors separated by commas
 * @param	{Function} filter function (optional)
 * @return {Array} Elements matched by any of the selectors and filtered by the filter function
 */
axe.utils.querySelectorAllFilter = function(domTree, selector, filter) {
	domTree = Array.isArray(domTree) ? domTree : [domTree];
	const expressions = axe.utils.convertSelector(selector);
	return matchExpressions(domTree, expressions, filter);
};
