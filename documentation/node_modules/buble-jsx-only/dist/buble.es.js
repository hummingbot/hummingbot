import MagicString from 'magic-string';
import { Parser } from 'acorn';
import acornJsx from 'acorn-jsx';
import acornDynamicImport from 'acorn-dynamic-import';

// used for debugging, without the noise created by
// circular references
function toJSON(node) {
	var obj = {};

	Object.keys(node).forEach(key => {
		if (
			key === 'parent' ||
			key === 'program' ||
			key === 'keys' ||
			key === '__wrapped'
		)
			{ return; }

		if (Array.isArray(node[key])) {
			obj[key] = node[key].map(toJSON);
		} else if (node[key] && node[key].toJSON) {
			obj[key] = node[key].toJSON();
		} else {
			obj[key] = node[key];
		}
	});

	return obj;
}

class Node {
	ancestor(level) {
		var node = this;
		while (level--) {
			node = node.parent;
			if (!node) { return null; }
		}

		return node;
	}

	contains(node) {
		while (node) {
			if (node === this) { return true; }
			node = node.parent;
		}

		return false;
	}

	findLexicalBoundary() {
		return this.parent.findLexicalBoundary();
	}

	findNearest(type) {
		if (typeof type === 'string') { type = new RegExp(`^${type}$`); }
		if (type.test(this.type)) { return this; }
		return this.parent.findNearest(type);
	}

	unparenthesizedParent() {
		var node = this.parent;
		while (node && node.type === 'ParenthesizedExpression') {
			node = node.parent;
		}
		return node;
	}

	unparenthesize() {
		var node = this;
		while (node.type === 'ParenthesizedExpression') {
			node = node.expression;
		}
		return node;
	}

	findScope(functionScope) {
		return this.parent.findScope(functionScope);
	}

	getIndentation() {
		return this.parent.getIndentation();
	}

	initialise(transforms) {
		for (var i = 0, list = this.keys; i < list.length; i += 1) {
			var key = list[i];

			var value = this[key];

			if (Array.isArray(value)) {
				value.forEach(node => node && node.initialise(transforms));
			} else if (value && typeof value === 'object') {
				value.initialise(transforms);
			}
		}
	}

	toJSON() {
		return toJSON(this);
	}

	toString() {
		return this.program.magicString.original.slice(this.start, this.end);
	}

	transpile(code, transforms) {
		for (var i = 0, list = this.keys; i < list.length; i += 1) {
			var key = list[i];

			var value = this[key];

			if (Array.isArray(value)) {
				value.forEach(node => node && node.transpile(code, transforms));
			} else if (value && typeof value === 'object') {
				value.transpile(code, transforms);
			}
		}
	}
}

function extractNames(node) {
	var names = [];
	extractors[node.type](names, node);
	return names;
}

var extractors = {
	Identifier(names, node) {
		names.push(node);
	},

	ObjectPattern(names, node) {
		for (var i = 0, list = node.properties; i < list.length; i += 1) {
			var prop = list[i];

			extractors[prop.type](names, prop);
		}
	},

	Property(names, node) {
		extractors[node.value.type](names, node.value);
	},

	ArrayPattern(names, node) {
		for (var i = 0, list = node.elements; i < list.length; i += 1) {
			var element = list[i];

			if (element) { extractors[element.type](names, element); }
		}
	},

	RestElement(names, node) {
		extractors[node.argument.type](names, node.argument);
	},

	AssignmentPattern(names, node) {
		extractors[node.left.type](names, node.left);
	}
};

var reserved = Object.create(null);
'do if in for let new try var case else enum eval null this true void with await break catch class const false super throw while yield delete export import public return static switch typeof default extends finally package private continue debugger function arguments interface protected implements instanceof'
	.split(' ')
	.forEach(word => (reserved[word] = true));

function Scope(options) {
	options = options || {};

	this.parent = options.parent;
	this.isBlockScope = !!options.block;
	this.createDeclarationCallback = options.declare;

	var scope = this;
	while (scope.isBlockScope) { scope = scope.parent; }
	this.functionScope = scope;

	this.identifiers = [];
	this.declarations = Object.create(null);
	this.references = Object.create(null);
	this.blockScopedDeclarations = this.isBlockScope ? null : Object.create(null);
	this.aliases = Object.create(null);
}

Scope.prototype = {
	addDeclaration(node, kind) {
		for (var i = 0, list = extractNames(node); i < list.length; i += 1) {
			var identifier = list[i];

			var name = identifier.name;

			var declaration = { name, node: identifier, kind, instances: [] };
			this.declarations[name] = declaration;

			if (this.isBlockScope) {
				if (!this.functionScope.blockScopedDeclarations[name])
					{ this.functionScope.blockScopedDeclarations[name] = []; }
				this.functionScope.blockScopedDeclarations[name].push(declaration);
			}
		}
	},

	addReference(identifier) {
		if (this.consolidated) {
			this.consolidateReference(identifier);
		} else {
			this.identifiers.push(identifier);
		}
	},

	consolidate() {
		for (var i = 0; i < this.identifiers.length; i += 1) {
			// we might push to the array during consolidation, so don't cache length
			var identifier = this.identifiers[i];
			this.consolidateReference(identifier);
		}

		this.consolidated = true; // TODO understand why this is necessary... seems bad
	},

	consolidateReference(identifier) {
		var declaration = this.declarations[identifier.name];
		if (declaration) {
			declaration.instances.push(identifier);
		} else {
			this.references[identifier.name] = true;
			if (this.parent) { this.parent.addReference(identifier); }
		}
	},

	contains(name) {
		return (
			this.declarations[name] ||
			(this.parent ? this.parent.contains(name) : false)
		);
	},

	createIdentifier(base) {
		if (typeof base === 'number') { base = base.toString(); }

		base = base
			.replace(/\s/g, '')
			.replace(/\[([^\]]+)\]/g, '_$1')
			.replace(/[^a-zA-Z0-9_$]/g, '_')
			.replace(/_{2,}/, '_');

		var name = base;
		var counter = 1;

		while (
			this.declarations[name] ||
			this.references[name] ||
			this.aliases[name] ||
			name in reserved
		) {
			name = `${base}$${counter++}`;
		}

		this.aliases[name] = true;
		return name;
	},

	createDeclaration(base) {
		var id = this.createIdentifier(base);
		this.createDeclarationCallback(id);
		return id;
	},

	findDeclaration(name) {
		return (
			this.declarations[name] ||
			(this.parent && this.parent.findDeclaration(name))
		);
	},

	// Sometimes, block scope declarations change name during transpilation
	resolveName(name) {
		var declaration = this.findDeclaration(name);
		return declaration ? declaration.name : name;
	}
};

function locate(source, index) {
	var lines = source.split('\n');
	var len = lines.length;

	var lineStart = 0;
	var i;

	for (i = 0; i < len; i += 1) {
		var line = lines[i];
		var lineEnd = lineStart + line.length + 1; // +1 for newline

		if (lineEnd > index) {
			return { line: i + 1, column: index - lineStart, char: i };
		}

		lineStart = lineEnd;
	}

	throw new Error('Could not determine location of character');
}

function pad(num, len) {
	var result = String(num);
	return result + repeat(' ', len - result.length);
}

function repeat(str, times) {
	var result = '';
	while (times--) { result += str; }
	return result;
}

function getSnippet(source, loc, length) {
	if ( length === void 0 ) length = 1;

	var first = Math.max(loc.line - 5, 0);
	var last = loc.line;

	var numDigits = String(last).length;

	var lines = source.split('\n').slice(first, last);

	var lastLine = lines[lines.length - 1];
	var offset = lastLine.slice(0, loc.column).replace(/\t/g, '  ').length;

	var snippet = lines
		.map((line, i) => `${pad(i + first + 1, numDigits)} : ${line.replace(/\t/g, '  ')}`)
		.join('\n');

	snippet += '\n' + repeat(' ', numDigits + 3 + offset) + repeat('^', length);

	return snippet;
}

class CompileError extends Error {
	constructor(message, node) {
		super(message);

		this.name = 'CompileError';
		if (!node) {
			return;
		}

		var source = node.program.magicString.original;
		var loc = locate(source, node.start);

		this.message = message + ` (${loc.line}:${loc.column})`;

		this.stack = new Error().stack.replace(
			new RegExp(`.+new ${this.name}.+\\n`, 'm'),
			''
		);

		this.loc = loc;
		this.snippet = getSnippet(source, loc, node.end - node.start);
	}

	toString() {
		return `${this.name}: ${this.message}\n${this.snippet}`;
	}

	static missingTransform(feature, transformKey, node, dangerousKey) {
		if ( dangerousKey === void 0 ) dangerousKey = null;

		var maybeDangerous = dangerousKey ? `, or \`transforms: { ${dangerousKey}: true }\` if you know what you're doing` : '';
		throw new CompileError(`Transforming ${feature} is not ${dangerousKey ? "fully supported" : "implemented"}. Use \`transforms: { ${transformKey}: false }\` to skip transformation and disable this error${maybeDangerous}.`, node);
	}
}

function findIndex(array, fn) {
	for (var i = 0; i < array.length; i += 1) {
		if (fn(array[i], i)) { return i; }
	}

	return -1;
}

var handlers = {
	Identifier: destructureIdentifier,
	AssignmentPattern: destructureAssignmentPattern,
	ArrayPattern: destructureArrayPattern,
	ObjectPattern: destructureObjectPattern
};

function destructure(
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
	var isIdentifier = node.left.type === 'Identifier';
	var name = isIdentifier ? node.left.name : ref;

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
	var c = node.start;

	node.elements.forEach((element, i) => {
		if (!element) { return; }

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
	var c = node.start;

	var nonRestKeys = [];
	node.properties.forEach(prop => {
		var value;
		var content;
		if (prop.type === 'Property') {
			content = prop.value;
			if (!prop.computed && prop.key.type === 'Identifier') {
				value = `${ref}.${prop.key.name}`;
				nonRestKeys.push(`"${prop.key.name}"`);
			} else if (!prop.computed && prop.key.type === 'Literal') {
				value = `${ref}[${prop.key.raw}]`;
				nonRestKeys.push(JSON.stringify(String(prop.key.value)));
			} else {
				var expr = code.slice(prop.key.start, prop.key.end);
				value = `${ref}[${expr}]`;
				nonRestKeys.push(`String(${expr})`);
			}
		} else if (prop.type === 'RestElement') {
			content = prop.argument;
			value = createIdentifier('rest');
			statementGenerators.push((start, prefix, suffix) => {
				var helper = prop.program.getObjectWithoutPropertiesHelper(code);
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
			var name;

			var isIdentifier = node.left.type === 'Identifier';

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

			var ref = value;
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
				var ref$1 = createIdentifier(value);

				statementGenerators.push((start, prefix, suffix) => {
					code.prependRight(node.start, (inline ? '' : `${prefix}var `) + `${ref$1} = `);
					code.overwrite(node.start, (c = node.start + 1), value, {
						contentOnly: true
					});
					code.appendLeft(c, suffix);

					code.move(node.start, c, start);
				});

				node.elements.forEach((element, i) => {
					if (!element) { return; }

					if (element.type === 'RestElement') {
						handleProperty(
							code,
							createIdentifier,
							resolveName,
							c,
							element.argument,
							`${ref$1}.slice(${i})`,
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
							`${ref$1}[${i}]`,
							inline,
							statementGenerators
						);
					}
					c = element.end;
				});
			} else {
				var index = findIndex(node.elements, Boolean);
				var element = node.elements[index];
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

function isUseStrict(node) {
	if (!node) { return false; }
	if (node.type !== 'ExpressionStatement') { return false; }
	if (node.expression.type !== 'Literal') { return false; }
	return node.expression.value === 'use strict';
}

class BlockStatement extends Node {
	createScope() {
		this.parentIsFunction = /Function/.test(this.parent.type);
		this.isFunctionBlock = this.parentIsFunction || this.parent.type === 'Root';
		this.scope = new Scope({
			block: !this.isFunctionBlock,
			parent: this.parent.findScope(false),
			declare: id => this.createdDeclarations.push(id)
		});

		if (this.parentIsFunction) {
			this.parent.params.forEach(node => {
				this.scope.addDeclaration(node, 'param');
			});
		}
	}

	initialise(transforms) {
		this.thisAlias = null;
		this.argumentsAlias = null;
		this.defaultParameters = [];
		this.createdDeclarations = [];

		// normally the scope gets created here, during initialisation,
		// but in some cases (e.g. `for` statements), we need to create
		// the scope early, as it pertains to both the init block and
		// the body of the statement
		if (!this.scope) { this.createScope(); }

		this.body.forEach(node => node.initialise(transforms));

		this.scope.consolidate();
	}

	findLexicalBoundary() {
		if (this.type === 'Program') { return this; }
		if (/^Function/.test(this.parent.type)) { return this; }

		return this.parent.findLexicalBoundary();
	}

	findScope(functionScope) {
		if (functionScope && !this.isFunctionBlock)
			{ return this.parent.findScope(functionScope); }
		return this.scope;
	}

	getArgumentsAlias() {
		if (!this.argumentsAlias) {
			this.argumentsAlias = this.scope.createIdentifier('arguments');
		}

		return this.argumentsAlias;
	}

	getArgumentsArrayAlias() {
		if (!this.argumentsArrayAlias) {
			this.argumentsArrayAlias = this.scope.createIdentifier('argsArray');
		}

		return this.argumentsArrayAlias;
	}

	getThisAlias() {
		if (!this.thisAlias) {
			this.thisAlias = this.scope.createIdentifier('this');
		}

		return this.thisAlias;
	}

	getIndentation() {
		if (this.indentation === undefined) {
			var source = this.program.magicString.original;

			var useOuter = this.synthetic || !this.body.length;
			var c = useOuter ? this.start : this.body[0].start;

			while (c && source[c] !== '\n') { c -= 1; }

			this.indentation = '';

			// eslint-disable-next-line no-constant-condition
			while (true) {
				c += 1;
				var char = source[c];

				if (char !== ' ' && char !== '\t') { break; }

				this.indentation += char;
			}

			var indentString = this.program.magicString.getIndentString();

			// account for dedented class constructors
			var parent = this.parent;
			while (parent) {
				if (parent.kind === 'constructor' && !parent.parent.parent.superClass) {
					this.indentation = this.indentation.replace(indentString, '');
				}

				parent = parent.parent;
			}

			if (useOuter) { this.indentation += indentString; }
		}

		return this.indentation;
	}

	transpile(code, transforms) {
		var indentation = this.getIndentation();

		var introStatementGenerators = [];

		if (this.argumentsAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				var assignment = `${prefix}var ${this.argumentsAlias} = arguments${
					suffix
				}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.thisAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				var assignment = `${prefix}var ${this.thisAlias} = this${suffix}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.argumentsArrayAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				var i = this.scope.createIdentifier('i');
				var assignment = `${prefix}var ${i} = arguments.length, ${
					this.argumentsArrayAlias
				} = Array(${i});\n${indentation}while ( ${i}-- ) ${
					this.argumentsArrayAlias
				}[${i}] = arguments[${i}]${suffix}`;
				code.appendLeft(start, assignment);
			});
		}

		if (/Function/.test(this.parent.type)) {
			this.transpileParameters(
				this.parent.params,
				code,
				transforms,
				indentation,
				introStatementGenerators
			);
		} else if ('CatchClause' === this.parent.type) {
			this.transpileParameters(
				[this.parent.param],
				code,
				transforms,
				indentation,
				introStatementGenerators
			);
		}

		if (transforms.letConst && this.isFunctionBlock) {
			this.transpileBlockScopedIdentifiers(code);
		}

		super.transpile(code, transforms);

		if (this.createdDeclarations.length) {
			introStatementGenerators.push((start, prefix, suffix) => {
				var assignment = `${prefix}var ${this.createdDeclarations.join(', ')}${suffix}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.synthetic) {
			if (this.parent.type === 'ArrowFunctionExpression') {
				var expr = this.body[0];

				if (introStatementGenerators.length) {
					code
						.appendLeft(this.start, `{`)
						.prependRight(this.end, `${this.parent.getIndentation()}}`);

					code.prependRight(expr.start, `\n${indentation}return `);
					code.appendLeft(expr.end, `;\n`);
				} else if (transforms.arrow) {
					code.prependRight(expr.start, `{ return `);
					code.appendLeft(expr.end, `; }`);
				}
			} else if (introStatementGenerators.length) {
				code.prependRight(this.start, `{`).appendLeft(this.end, `}`);
			}
		}

		var start;
		if (isUseStrict(this.body[0])) {
			start = this.body[0].end;
		} else if (this.synthetic || this.parent.type === 'Root') {
			start = this.start;
		} else {
			start = this.start + 1;
		}

		var prefix = `\n${indentation}`;
		var suffix = ';';
		introStatementGenerators.forEach((fn, i) => {
			if (i === introStatementGenerators.length - 1) { suffix = `;\n`; }
			fn(start, prefix, suffix);
		});
	}

	transpileParameters(params, code, transforms, indentation, introStatementGenerators) {
		params.forEach(param => {
			if (
				param.type === 'AssignmentPattern' &&
				param.left.type === 'Identifier'
			) {
				if (transforms.defaultParameter) {
					introStatementGenerators.push((start, prefix, suffix) => {
						var lhs = `${prefix}if ( ${param.left.name} === void 0 ) ${
							param.left.name
						}`;

						code
							.prependRight(param.left.end, lhs)
							.move(param.left.end, param.right.end, start)
							.appendLeft(param.right.end, suffix);
					});
				}
			} else if (param.type === 'RestElement') {
				if (transforms.spreadRest) {
					introStatementGenerators.push((start, prefix, suffix) => {
						var penultimateParam = params[params.length - 2];

						if (penultimateParam) {
							code.remove(
								penultimateParam ? penultimateParam.end : param.start,
								param.end
							);
						} else {
							var start$1 = param.start,
								end = param.end; // TODO https://gitlab.com/Rich-Harris/buble/issues/8

							while (/\s/.test(code.original[start$1 - 1])) { start$1 -= 1; }
							while (/\s/.test(code.original[end])) { end += 1; }

							code.remove(start$1, end);
						}

						var name = param.argument.name;
						var len = this.scope.createIdentifier('len');
						var count = params.length - 1;

						if (count) {
							code.prependRight(
								start,
								`${prefix}var ${name} = [], ${len} = arguments.length - ${
									count
								};\n${indentation}while ( ${len}-- > 0 ) ${name}[ ${
									len
								} ] = arguments[ ${len} + ${count} ]${suffix}`
							);
						} else {
							code.prependRight(
								start,
								`${prefix}var ${name} = [], ${len} = arguments.length;\n${
									indentation
								}while ( ${len}-- ) ${name}[ ${len} ] = arguments[ ${len} ]${
									suffix
								}`
							);
						}
					});
				}
			} else if (param.type !== 'Identifier') {
				if (transforms.parameterDestructuring) {
					var ref = this.scope.createIdentifier('ref');
					destructure(
						code,
						id => this.scope.createIdentifier(id),
						(ref) => {
							var name = ref.name;

							return this.scope.resolveName(name);
					},
						param,
						ref,
						false,
						introStatementGenerators
					);
					code.prependRight(param.start, ref);
				}
			}
		});
	}

	transpileBlockScopedIdentifiers(code) {
		Object.keys(this.scope.blockScopedDeclarations).forEach(name => {
			var declarations = this.scope.blockScopedDeclarations[name];

			for (var i$2 = 0, list$2 = declarations; i$2 < list$2.length; i$2 += 1) {
				var declaration = list$2[i$2];

				var cont = false; // TODO implement proper continue...

				if (declaration.kind === 'for.let') {
					// special case
					var forStatement = declaration.node.findNearest('ForStatement');

					if (forStatement.shouldRewriteAsFunction) {
						var outerAlias = this.scope.createIdentifier(name);
						var innerAlias = forStatement.reassigned[name]
							? this.scope.createIdentifier(name)
							: name;

						declaration.name = outerAlias;
						code.overwrite(
							declaration.node.start,
							declaration.node.end,
							outerAlias,
							{ storeName: true }
						);

						forStatement.aliases[name] = {
							outer: outerAlias,
							inner: innerAlias
						};

						for (var i = 0, list = declaration.instances; i < list.length; i += 1) {
							var identifier = list[i];

							var alias = forStatement.body.contains(identifier)
								? innerAlias
								: outerAlias;

							if (name !== alias) {
								code.overwrite(identifier.start, identifier.end, alias, {
									storeName: true
								});
							}
						}

						cont = true;
					}
				}

				if (!cont) {
					var alias$1 = this.scope.createIdentifier(name);

					if (name !== alias$1) {
						declaration.name = alias$1;
						code.overwrite(
							declaration.node.start,
							declaration.node.end,
							alias$1,
							{ storeName: true }
						);

						for (var i$1 = 0, list$1 = declaration.instances; i$1 < list$1.length; i$1 += 1) {
							var identifier$1 = list$1[i$1];

							identifier$1.rewritten = true;
							code.overwrite(identifier$1.start, identifier$1.end, alias$1, {
								storeName: true
							});
						}
					}
				}
			}
		});
	}
}

var hasDashes = val => /-/.test(val);

var formatKey = key => (hasDashes(key) ? `'${key}'` : key);

var formatVal = val => (val ? '' : 'true');

class JSXAttribute extends Node {
	transpile(code, transforms) {
		var ref = this.name;
		var start = ref.start;
		var name = ref.name;

		// Overwrite equals sign if value is present.
		var end = this.value ? this.value.start : this.name.end;

		code.overwrite(start, end, `${formatKey(name)}: ${formatVal(this.value)}`);

		super.transpile(code, transforms);
	}
}

function containsNewLine(node) {
	return (
		node.type === 'JSXText' && !/\S/.test(node.value) && /\n/.test(node.value)
	);
}

class JSXClosingElement extends Node {
	transpile(code) {
		var spaceBeforeParen = true;

		var lastChild = this.parent.children[this.parent.children.length - 1];

		// omit space before closing paren if
		//   a) this is on a separate line, or
		//   b) there are no children but there are attributes
		if (
			(lastChild && containsNewLine(lastChild)) ||
			this.parent.openingElement.attributes.length
		) {
			spaceBeforeParen = false;
		}

		code.overwrite(this.start, this.end, spaceBeforeParen ? ' )' : ')');
	}
}

function containsNewLine$1(node) {
	return (
		node.type === 'JSXText' && !/\S/.test(node.value) && /\n/.test(node.value)
	);
}

class JSXClosingFragment extends Node {
	transpile(code) {
		var spaceBeforeParen = true;

		var lastChild = this.parent.children[this.parent.children.length - 1];

		// omit space before closing paren if this is on a separate line
		if (lastChild && containsNewLine$1(lastChild)) {
			spaceBeforeParen = false;
		}

		code.overwrite(this.start, this.end, spaceBeforeParen ? ' )' : ')');
	}
}

function normalise(str, removeTrailingWhitespace) {

	str = str.replace(/\u00a0/g, '&nbsp;');

	if (removeTrailingWhitespace && /\n/.test(str)) {
		str = str.replace(/\s+$/, '');
	}

	str = str
		.replace(/^\n\r?\s+/, '') // remove leading newline + space
		.replace(/\s*\n\r?\s*/gm, ' '); // replace newlines with spaces

	// TODO prefer single quotes?
	return JSON.stringify(str);
}

class JSXElement extends Node {
	transpile(code, transforms) {
		super.transpile(code, transforms);

		var children = this.children.filter(child => {
			if (child.type !== 'JSXText') { return true; }

			// remove whitespace-only literals, unless on a single line
			return /\S/.test(child.raw) || !/\n/.test(child.raw);
		});

		if (children.length) {
			var c = (this.openingElement || this.openingFragment).end;

			var i;
			for (i = 0; i < children.length; i += 1) {
				var child = children[i];

				if (
					child.type === 'JSXExpressionContainer' &&
					child.expression.type === 'JSXEmptyExpression'
				) ; else {
					var tail =
						code.original[c] === '\n' && child.type !== 'JSXText' ? '' : ' ';
					code.appendLeft(c, `,${tail}`);
				}

				if (child.type === 'JSXText') {
					var str = normalise(child.value, i === children.length - 1);
					code.overwrite(child.start, child.end, str);
				}

				c = child.end;
			}
		}
	}
}

class JSXExpressionContainer extends Node {
	transpile(code, transforms) {
		code.remove(this.start, this.expression.start);
		code.remove(this.expression.end, this.end);

		super.transpile(code, transforms);
	}
}

class JSXFragment extends JSXElement {
}

class JSXOpeningElement extends Node {
	transpile(code, transforms) {
		super.transpile(code, transforms);

		code.overwrite(this.start, this.name.start, `${this.program.jsx}( `);

		var html =
			this.name.type === 'JSXIdentifier' &&
			this.name.name[0] === this.name.name[0].toLowerCase();
		if (html) { code.prependRight(this.name.start, `'`); }

		var len = this.attributes.length;
		var c = this.name.end;

		if (len) {
			var i;

			var hasSpread = false;
			for (i = 0; i < len; i += 1) {
				if (this.attributes[i].type === 'JSXSpreadAttribute') {
					hasSpread = true;
					break;
				}
			}

			c = this.attributes[0].end;

			for (i = 0; i < len; i += 1) {
				var attr = this.attributes[i];

				if (i > 0) {
					if (attr.start === c) { code.prependRight(c, ', '); }
					else { code.overwrite(c, attr.start, ', '); }
				}

				if (hasSpread && attr.type !== 'JSXSpreadAttribute') {
					var lastAttr = this.attributes[i - 1];
					var nextAttr = this.attributes[i + 1];

					if (!lastAttr || lastAttr.type === 'JSXSpreadAttribute') {
						code.prependRight(attr.start, '{ ');
					}

					if (!nextAttr || nextAttr.type === 'JSXSpreadAttribute') {
						code.appendLeft(attr.end, ' }');
					}
				}

				c = attr.end;
			}

			var after;
			var before;
			if (hasSpread) {
				if (len === 1) {
					before = html ? `',` : ',';
				} else {
					if (!this.program.options.objectAssign) {
						throw new CompileError(
							"Mixed JSX attributes ending in spread requires specified objectAssign option with 'Object.assign' or polyfill helper.",
							this
						);
					}
					before = html
						? `', ${this.program.options.objectAssign}({},`
						: `, ${this.program.options.objectAssign}({},`;
					after = ')';
				}
			} else {
				before = html ? `', {` : ', {';
				after = ' }';
			}

			code.prependRight(this.name.end, before);

			if (after) {
				code.appendLeft(this.attributes[len - 1].end, after);
			}
		} else {
			code.appendLeft(this.name.end, html ? `', null` : `, null`);
			c = this.name.end;
		}

		if (this.selfClosing) {
			code.overwrite(c, this.end, this.attributes.length ? `)` : ` )`);
		} else {
			code.remove(c, this.end);
		}
	}
}

class JSXOpeningFragment extends Node {
	transpile(code) {
		code.overwrite(this.start, this.end, `${this.program.jsx}( ${this.program.jsxFragment}, null`);
	}
}

class JSXSpreadAttribute extends Node {
	transpile(code, transforms) {
		code.remove(this.start, this.argument.start);
		code.remove(this.argument.end, this.end);

		super.transpile(code, transforms);
	}
}

var types = {
	JSXAttribute,
	JSXClosingElement,
	JSXClosingFragment,
	JSXElement,
	JSXExpressionContainer,
	JSXFragment,
	JSXOpeningElement,
	JSXOpeningFragment,
	JSXSpreadAttribute,
};

var keys = {
	Program: ['body'],
	Literal: []
};

var statementsWithBlocks = {
	IfStatement: 'consequent',
	ForStatement: 'body',
	ForInStatement: 'body',
	ForOfStatement: 'body',
	WhileStatement: 'body',
	DoWhileStatement: 'body',
	ArrowFunctionExpression: 'body'
};

function wrap(raw, parent) {
	if (!raw) { return; }

	if ('length' in raw) {
		var i = raw.length;
		while (i--) { wrap(raw[i], parent); }
		return;
	}

	// with e.g. shorthand properties, key and value are
	// the same node. We don't want to wrap an object twice
	if (raw.__wrapped) { return; }
	raw.__wrapped = true;

	if (!keys[raw.type]) {
		keys[raw.type] = Object.keys(raw).filter(
			key => typeof raw[key] === 'object'
		);
	}

	// special case – body-less if/for/while statements. TODO others?
	var bodyType = statementsWithBlocks[raw.type];
	if (bodyType && raw[bodyType].type !== 'BlockStatement') {
		var expression = raw[bodyType];

		// create a synthetic block statement, otherwise all hell
		// breaks loose when it comes to block scoping
		raw[bodyType] = {
			start: expression.start,
			end: expression.end,
			type: 'BlockStatement',
			body: [expression],
			synthetic: true
		};
	}

	raw.parent = parent;
	raw.program = parent.program || parent;
	raw.depth = parent.depth + 1;
	raw.keys = keys[raw.type];
	raw.indentation = undefined;

	for (var i$1 = 0, list = keys[raw.type]; i$1 < list.length; i$1 += 1) {
		var key = list[i$1];

		wrap(raw[key], raw);
	}

	raw.program.magicString.addSourcemapLocation(raw.start);
	raw.program.magicString.addSourcemapLocation(raw.end);

	var type =
		(raw.type === 'BlockStatement' ? BlockStatement : types[raw.type]) || Node;
	raw.__proto__ = type.prototype;
}

function Program(source, ast, transforms, options) {
	this.type = 'Root';

	// options
	this.jsx = options.jsx || 'React.createElement';
	this.jsxFragment = options.jsxFragment || 'React.Fragment';
	this.options = options;

	this.source = source;
	this.magicString = new MagicString(source);

	this.ast = ast;
	this.depth = 0;

	wrap((this.body = ast), this);
	this.body.__proto__ = BlockStatement.prototype;

	this.templateLiteralQuasis = Object.create(null);
	for (var i = 0; i < this.body.body.length; ++i) {
		if (!this.body.body[i].directive) {
			this.prependAt = this.body.body[i].start;
			break;
		}
	}
	this.objectWithoutPropertiesHelper = null;

	this.indentExclusionElements = [];
	this.body.initialise(transforms);

	this.indentExclusions = Object.create(null);
	for (var i$2 = 0, list = this.indentExclusionElements; i$2 < list.length; i$2 += 1) {
		var node = list[i$2];

		for (var i$1 = node.start; i$1 < node.end; i$1 += 1) {
			this.indentExclusions[i$1] = true;
		}
	}

	this.body.transpile(this.magicString, transforms);
}

Program.prototype = {
	export(options) {
		if ( options === void 0 ) options = {};

		return {
			code: this.magicString.toString(),
			map: this.magicString.generateMap({
				file: options.file,
				source: options.source,
				includeContent: options.includeContent !== false
			})
		};
	},

	findNearest() {
		return null;
	},

	findScope() {
		return null;
	},

	getObjectWithoutPropertiesHelper(code) {
		if (!this.objectWithoutPropertiesHelper) {
			this.objectWithoutPropertiesHelper = this.body.scope.createIdentifier('objectWithoutProperties');
			code.prependLeft(this.prependAt, `function ${this.objectWithoutPropertiesHelper} (obj, exclude) { ` +
				`var target = {}; for (var k in obj) ` +
				`if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) ` +
				`target[k] = obj[k]; return target; }\n`
			);
		}
		return this.objectWithoutPropertiesHelper;
	}
};

var matrix = {
	chrome: {
		    48: 0b00010010101000110011111,
		    49: 0b00010011111001111111111,
		    50: 0b00010111111001111111111,
		    51: 0b00010111111001111111111,
		    52: 0b00011111111001111111111,
		    53: 0b00011111111001111111111,
		    54: 0b00011111111001111111111,
		    55: 0b01011111111001111111111,
		    56: 0b01011111111001111111111,
		    57: 0b01011111111001111111111,
		    58: 0b01111111111001111111111,
		    59: 0b01111111111001111111111,
		    60: 0b11111111111001111111111,
		    61: 0b11111111111001111111111,
		    62: 0b11111111111001111111111,
		    63: 0b11111111111001111111111,
		    64: 0b11111111111001111111111,
		    65: 0b11111111111001111111111,
		    66: 0b11111111111001111111111,
		    67: 0b11111111111001111111111,
		    68: 0b11111111111001111111111,
		    69: 0b11111111111001111111111,
		    70: 0b11111111111001111111111,
		    71: 0b11111111111001111111111
	},
	firefox: {
		    43: 0b00010011101000110111011,
		    44: 0b00010011101000110111011,
		    45: 0b00010011101000110111111,
		    46: 0b00010111101000110111111,
		    47: 0b00010111101000111111111,
		    48: 0b00010111101000111111111,
		    49: 0b00010111101000111111111,
		    50: 0b00010111101000111111111,
		    51: 0b00010111101001111111111,
		    52: 0b01111111111001111111111,
		    53: 0b01111111111001111111111,
		    54: 0b01111111111001111111111,
		    55: 0b11111111111001111111111,
		    56: 0b11111111111001111111111,
		    57: 0b11111111111001111111111,
		    58: 0b11111111111001111111111,
		    59: 0b11111111111001111111111,
		    60: 0b11111111111001111111111,
		    61: 0b11111111111001111111111,
		    62: 0b11111111111001111111111,
		    63: 0b11111111111001111111111,
		    64: 0b11111111111001111111111
	},
	safari: {
		     8: 0b00010000000000000001001,
		     9: 0b00010010001000011011101,
		    10: 0b00110111111001111111111,
		'10.1': 0b01111111111001111111111,
		    11: 0b01111111111001111111111,
		'11.1': 0b11111111111001111111111,
		    12: 0b11111111111001111111111
	},
	ie: {
		     8: 0b00000000000000000000000,
		     9: 0b00010000000000000000001,
		    10: 0b00010000000000000000001,
		    11: 0b00010000000000000000001 // no let/const in for loops
	},
	edge: {
		    12: 0b00010010101000010011011,
		    13: 0b00010111101000110011111,
		    14: 0b00111111101001111111111,
		    15: 0b01111111101001111111111,
		    16: 0b01111111101001111111111,
		    17: 0b01111111101001111111111,
		    18: 0b01111111101001111111111,
		    19: 0b01111111101001111111111
	},
	node: {
		'0.10': 0b00010000000000000000001,
		'0.12': 0b00010000000000010000001,
		     4: 0b00010010001000110011111,
		     5: 0b00010010001000110011111,
		     6: 0b00010111111001111111111,
		     8: 0b01111111111001111111111,
		 '8.3': 0b11111111111001111111111,
		 '8.7': 0b11111111111001111111111,
		'8.10': 0b11111111111001111111111
	}
};

var features = [
	'getterSetter',
	'arrow',
	'classes',
	'computedProperty',
	'conciseMethodProperty',
	'defaultParameter',
	'destructuring',
	'forOf',
	'generator',
	'letConst',
	'moduleExport',
	'moduleImport',
	'numericLiteral',
	'parameterDestructuring',
	'spreadRest',
	'stickyRegExp',
	'templateString',
	'unicodeRegExp',

	// ES2016
	'exponentiation',

	// additional transforms, not from
	// https://featuretests.io
	'reservedProperties',

	'trailingFunctionCommas',
	'asyncAwait',
	'objectRestSpread'
];

var version = "0.19.8";

var parser = Parser.extend(acornDynamicImport, acornJsx());

var dangerousTransforms = ['dangerousTaggedTemplateString', 'dangerousForOf'];

function target(target) {
	var targets = Object.keys(target);
	var bitmask = targets.length
		? 0b11111111111111111111111
		: 0b00010000000000000000001;

	Object.keys(target).forEach(environment => {
		var versions = matrix[environment];
		if (!versions)
			{ throw new Error(
				`Unknown environment '${environment}'. Please raise an issue at https://github.com/bublejs/buble/issues`
			); }

		var targetVersion = target[environment];
		if (!(targetVersion in versions))
			{ throw new Error(
				`Support data exists for the following versions of ${environment}: ${Object.keys(
					versions
				).join(
					', '
				)}. Please raise an issue at https://github.com/bublejs/buble/issues`
			); }
		var support = versions[targetVersion];

		bitmask &= support;
	});

	var transforms = Object.create(null);
	features.forEach((name, i) => {
		transforms[name] = !(bitmask & (1 << i));
	});

	dangerousTransforms.forEach(name => {
		transforms[name] = false;
	});

	return transforms;
}

function transform(source, options) {
	if ( options === void 0 ) options = {};

	var ast;
	var jsx = null;

	try {
		ast = parser.parse(source, {
			ecmaVersion: 10,
			preserveParens: true,
			sourceType: 'module',
			allowAwaitOutsideFunction: true,
			allowReturnOutsideFunction: true,
			allowHashBang: true,
			onComment: (block, text) => {
				if (!jsx) {
					var match = /@jsx\s+([^\s]+)/.exec(text);
					if (match) { jsx = match[1]; }
				}
			}
		});
		options.jsx = jsx || options.jsx;
	} catch (err) {
		err.snippet = getSnippet(source, err.loc);
		err.toString = () => `${err.name}: ${err.message}\n${err.snippet}`;
		throw err;
	}

	var transforms = target(options.target || {});
	Object.keys(options.transforms || {}).forEach(name => {
		if (name === 'modules') {
			if (!('moduleImport' in options.transforms))
				{ transforms.moduleImport = options.transforms.modules; }
			if (!('moduleExport' in options.transforms))
				{ transforms.moduleExport = options.transforms.modules; }
			return;
		}

		if (!(name in transforms)) { throw new Error(`Unknown transform '${name}'`); }
		transforms[name] = options.transforms[name];
	});
	if (options.objectAssign === true) { options.objectAssign = 'Object.assign'; }
	return new Program(source, ast, transforms, options).export(options);
}

export { target, transform, version as VERSION };
//# sourceMappingURL=buble.es.js.map
