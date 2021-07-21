import CompileError from './CompileError.js';

export function isArguments(node) {
	return node.type === 'Identifier' && node.name === 'arguments';
}

export function inlineSpreads(
	code,
	node,
	elements
) {
	let i = elements.length;

	while (i--) {
		const element = elements[i];
		if (!element || element.type !== 'SpreadElement') {
			continue;
		}
		const argument = element.argument;
		if (argument.type !== 'ArrayExpression') {
			continue;
		}
		const subelements = argument.elements;
		if (subelements.some(subelement => subelement === null)) {
			// Not even going to try inlining spread arrays with holes.
			// It's a lot of work (got to be VERY careful in comma counting for
			// ArrayExpression, and turn blanks into undefined for
			// CallExpression and NewExpression), and probably literally no one
			// would ever benefit from it.
			continue;
		}
		// We can inline it: drop the `...[` and `]` and sort out any commas.
		const isLast = i === elements.length - 1;
		if (subelements.length === 0) {
			code.remove(
				isLast && i !== 0
					? elements[i - 1].end  // Take the previous comma too
					: element.start,
				isLast
					? node.end - 1  // Must remove trailing comma; element.end wouldn’t
					: elements[i + 1].start);
		} else {
			// Strip the `...[` and the `]` with a possible trailing comma before it,
			// leaving just the possible trailing comma after it.
			code.remove(element.start, subelements[0].start);
			code.remove(
				// Strip a possible trailing comma after the last element
				subelements[subelements.length - 1].end,
				// And also a possible trailing comma after the spread
				isLast
					? node.end - 1
					: element.end
			);
		}
		elements.splice(i, 1, ...subelements);
		i += subelements.length;
	}
}

// Returns false if it’s safe to simply append a method call to the node,
// e.g. `a` → `a.concat()`.
//
// Returns true if it may not be and so parentheses should be employed,
// e.g. `a ? b : c` → `a ? b : c.concat()` would be wrong.
//
// This test may be overcautious; if desired it can be refined over time.
export function needsParentheses(node) {
	switch (node.type) {
		// Currently whitelisted are all relevant ES5 node types ('Literal' and
		// 'ObjectExpression' are skipped as irrelevant for array/call spread.)
		case 'ArrayExpression':
		case 'CallExpression':
		case 'Identifier':
		case 'ParenthesizedExpression':
		case 'ThisExpression':
			return false;
		default:
			return true;
	}
}

export default function spread(
	code,
	elements,
	start,
	argumentsArrayAlias,
	isNew
) {
	let i = elements.length;
	let firstSpreadIndex = -1;

	while (i--) {
		const element = elements[i];
		if (element && element.type === 'SpreadElement') {
			if (isArguments(element.argument)) {
				code.overwrite(
					element.argument.start,
					element.argument.end,
					argumentsArrayAlias
				);
			}

			firstSpreadIndex = i;
		}
	}

	if (firstSpreadIndex === -1) return false; // false indicates no spread elements

	if (isNew) {
		for (i = 0; i < elements.length; i += 1) {
			const element = elements[i];
			if (element.type === 'SpreadElement') {
				code.remove(element.start, element.argument.start);
			} else {
				code.prependRight(element.start, '[');
				code.prependRight(element.end, ']');
			}
		}

		return true; // true indicates some spread elements
	}

	let element = elements[firstSpreadIndex];
	const previousElement = elements[firstSpreadIndex - 1];

	if (!previousElement) {
		// We may need to parenthesize it to handle ternaries like [...a ? b : c].
		let addClosingParen;
		if (start !== element.start) {
			if ((addClosingParen = needsParentheses(element.argument))) {
				code.overwrite(start, element.start, '( ');
			} else {
				code.remove(start, element.start);
			}
		} else if (element.parent.type === 'CallExpression') {
			// CallExpression inserts `( ` itself, we add the ).
			// (Yeah, CallExpression did the needsParentheses call already,
			// but we don’t have its result handy, so do it again. It’s cheap.)
			addClosingParen = needsParentheses(element.argument);
		} else {
			// Should be unreachable, but doing this is more robust.
			throw new CompileError(
				'Unsupported spread construct, please raise an issue at https://github.com/bublejs/buble/issues',
				element
			);
		}
		code.overwrite(element.end, elements[1].start,
			addClosingParen ? ' ).concat( ' : '.concat( ');
	} else {
		code.overwrite(previousElement.end, element.start, ' ].concat( ');
	}

	for (i = firstSpreadIndex; i < elements.length; i += 1) {
		element = elements[i];

		if (element) {
			if (element.type === 'SpreadElement') {
				code.remove(element.start, element.argument.start);
			} else {
				code.appendLeft(element.start, '[');
				code.appendLeft(element.end, ']');
			}
		}
	}

	return true; // true indicates some spread elements
}
