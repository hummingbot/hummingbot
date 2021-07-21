import CompileError from '../utils/CompileError.js';
import { findIndex } from './array.js';

const handlers = {
	Identifier: destructureIdentifier,
	AssignmentPattern: destructureAssignmentPattern,
	ArrayPattern: destructureArrayPattern,
	ObjectPattern: destructureObjectPattern
};

export default function destructure(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	handlers[node.type](code, createIdentifier, resolveName, node, ref, inline, statementGenerators);
}

function destructureIdentifier(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	statementGenerators.push((start, prefix, suffix) => {
		code.overwrite(node.start, node.end, (inline ? prefix : `${prefix}var `) + resolveName(node) + ` = ${ref}${suffix}`);
		code.move(node.start, node.end, start);
	});
}

function destructureMemberExpression(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	statementGenerators.push((start, prefix, suffix) => {
		code.prependRight(node.start, inline ? prefix : `${prefix}var `);
		code.appendLeft(node.end, ` = ${ref}${suffix}`);
		code.move(node.start, node.end, start);
	});
}

function destructureAssignmentPattern(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	const isIdentifier = node.left.type === 'Identifier';
	const name = isIdentifier ? node.left.name : ref;

	if (!inline) {
		statementGenerators.push((start, prefix, suffix) => {
			code.prependRight(
				node.left.end,
				`${prefix}if ( ${name} === void 0 ) ${name}`
			);
			code.move(node.left.end, node.right.end, start);
			code.appendLeft(node.right.end, suffix);
		});
	}

	if (!isIdentifier) {
		destructure(code, createIdentifier, resolveName, node.left, ref, inline, statementGenerators);
	}
}

function destructureArrayPattern(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	let c = node.start;

	node.elements.forEach((element, i) => {
		if (!element) return;

		if (element.type === 'RestElement') {
			handleProperty(
				code,
				createIdentifier,
				resolveName,
				c,
				element.argument,
				`${ref}.slice(${i})`,
				inline,
				statementGenerators
			);
		} else {
			handleProperty(
				code,
				createIdentifier,
				resolveName,
				c,
				element,
				`${ref}[${i}]`,
				inline,
				statementGenerators
			);
		}
		c = element.end;
	});

	code.remove(c, node.end);
}

function destructureObjectPattern(
	code,
	createIdentifier,
	resolveName,
	node,
	ref,
	inline,
	statementGenerators
) {
	let c = node.start;

	const nonRestKeys = [];
	node.properties.forEach(prop => {
		let value;
		let content;
		if (prop.type === 'Property') {
			content = prop.value;
			if (!prop.computed && prop.key.type === 'Identifier') {
				value = `${ref}.${prop.key.name}`;
				nonRestKeys.push(`"${prop.key.name}"`);
			} else if (!prop.computed && prop.key.type === 'Literal') {
				value = `${ref}[${prop.key.raw}]`;
				nonRestKeys.push(JSON.stringify(String(prop.key.value)));
			} else {
				const expr = code.slice(prop.key.start, prop.key.end);
				value = `${ref}[${expr}]`;
				nonRestKeys.push(`String(${expr})`);
			}
		} else if (prop.type === 'RestElement') {
			content = prop.argument;
			value = createIdentifier('rest');
			statementGenerators.push((start, prefix, suffix) => {
				const helper = prop.program.getObjectWithoutPropertiesHelper(code);
				code.overwrite(
					prop.start,
					(c = prop.argument.start),
					(inline ? prefix : `${prefix}var `) + `${value} = ${helper}( ${ref}, [${nonRestKeys.join(', ')}] )${suffix}`
				);
				code.move(prop.start, c, start);
			});
		} else {
			throw new CompileError(
				this,
				`Unexpected node of type ${prop.type} in object pattern`
			);
		}
		handleProperty(code, createIdentifier, resolveName, c, content, value, inline, statementGenerators);
		c = prop.end;
	});

	code.remove(c, node.end);
}

function handleProperty(
	code,
	createIdentifier,
	resolveName,
	c,
	node,
	value,
	inline,
	statementGenerators
) {
	switch (node.type) {
		case 'Identifier': {
			code.remove(c, node.start);
			destructureIdentifier(
				code,
				createIdentifier,
				resolveName,
				node,
				value,
				inline,
				statementGenerators
			);
			break;
		}

		case 'MemberExpression':
			code.remove(c, node.start);
			destructureMemberExpression(
				code,
				createIdentifier,
				resolveName,
				node,
				value,
				true,
				statementGenerators
			);
			break;

		case 'AssignmentPattern': {
			let name;

			const isIdentifier = node.left.type === 'Identifier';

			if (isIdentifier) {
				name = resolveName(node.left);
			} else {
				name = createIdentifier(value);
			}

			statementGenerators.push((start, prefix, suffix) => {
				if (inline) {
					code.prependRight(
						node.right.start,
						`${name} = ${value}, ${name} = ${name} === void 0 ? `
					);
					code.appendLeft(node.right.end, ` : ${name}${suffix}`);
				} else {
					code.prependRight(
						node.right.start,
						`${prefix}var ${name} = ${value}; if ( ${name} === void 0 ) ${name} = `
					);
					code.appendLeft(node.right.end, suffix);
				}

				code.move(node.right.start, node.right.end, start);
			});

			if (isIdentifier) {
				code.remove(c, node.right.start);
			} else {
				code.remove(c, node.left.start);
				code.remove(node.left.end, node.right.start);
				handleProperty(
					code,
					createIdentifier,
					resolveName,
					c,
					node.left,
					name,
					inline,
					statementGenerators
				);
			}

			break;
		}

		case 'ObjectPattern': {
			code.remove(c, (c = node.start));

			let ref = value;
			if (node.properties.length > 1) {
				ref = createIdentifier(value);

				statementGenerators.push((start, prefix, suffix) => {
					// this feels a tiny bit hacky, but we can't do a
					// straightforward appendLeft and keep correct order...
					code.prependRight(node.start, (inline ? '' : `${prefix}var `) + `${ref} = `);
					code.overwrite(node.start, (c = node.start + 1), value);
					code.appendLeft(c, suffix);

					code.overwrite(
						node.start,
						(c = node.start + 1),
						(inline ? '' : `${prefix}var `) + `${ref} = ${value}${suffix}`
					);
					code.move(node.start, c, start);
				});
			}

			destructureObjectPattern(
				code,
				createIdentifier,
				resolveName,
				node,
				ref,
				inline,
				statementGenerators
			);

			break;
		}

		case 'ArrayPattern': {
			code.remove(c, (c = node.start));

			if (node.elements.filter(Boolean).length > 1) {
				const ref = createIdentifier(value);

				statementGenerators.push((start, prefix, suffix) => {
					code.prependRight(node.start, (inline ? '' : `${prefix}var `) + `${ref} = `);
					code.overwrite(node.start, (c = node.start + 1), value, {
						contentOnly: true
					});
					code.appendLeft(c, suffix);

					code.move(node.start, c, start);
				});

				node.elements.forEach((element, i) => {
					if (!element) return;

					if (element.type === 'RestElement') {
						handleProperty(
							code,
							createIdentifier,
							resolveName,
							c,
							element.argument,
							`${ref}.slice(${i})`,
							inline,
							statementGenerators
						);
					} else {
						handleProperty(
							code,
							createIdentifier,
							resolveName,
							c,
							element,
							`${ref}[${i}]`,
							inline,
							statementGenerators
						);
					}
					c = element.end;
				});
			} else {
				const index = findIndex(node.elements, Boolean);
				const element = node.elements[index];
				if (element.type === 'RestElement') {
					handleProperty(
						code,
						createIdentifier,
						resolveName,
						c,
						element.argument,
						`${value}.slice(${index})`,
						inline,
						statementGenerators
					);
				} else {
					handleProperty(
						code,
						createIdentifier,
						resolveName,
						c,
						element,
						`${value}[${index}]`,
						inline,
						statementGenerators
					);
				}
				c = element.end;
			}

			code.remove(c, node.end);
			break;
		}

		default: {
			throw new Error(`Unexpected node type in destructuring (${node.type})`);
		}
	}
}
