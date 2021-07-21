'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

function _interopDefault (ex) { return (ex && (typeof ex === 'object') && 'default' in ex) ? ex['default'] : ex; }

var MagicString = _interopDefault(require('magic-string'));
var acorn = require('acorn');
var acornJsx = _interopDefault(require('acorn-jsx'));
var acornDynamicImport = _interopDefault(require('acorn-dynamic-import'));

// used for debugging, without the noise created by
// circular references
function toJSON(node) {
	var obj = {};

	Object.keys(node).forEach(function (key) {
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

var Node = function Node () {};

Node.prototype.ancestor = function ancestor (level) {
	var node = this;
	while (level--) {
		node = node.parent;
		if (!node) { return null; }
	}

	return node;
};

Node.prototype.contains = function contains (node) {
	while (node) {
		if (node === this) { return true; }
		node = node.parent;
	}

	return false;
};

Node.prototype.findLexicalBoundary = function findLexicalBoundary () {
	return this.parent.findLexicalBoundary();
};

Node.prototype.findNearest = function findNearest (type) {
	if (typeof type === 'string') { type = new RegExp(("^" + type + "$")); }
	if (type.test(this.type)) { return this; }
	return this.parent.findNearest(type);
};

Node.prototype.unparenthesizedParent = function unparenthesizedParent () {
	var node = this.parent;
	while (node && node.type === 'ParenthesizedExpression') {
		node = node.parent;
	}
	return node;
};

Node.prototype.unparenthesize = function unparenthesize () {
	var node = this;
	while (node.type === 'ParenthesizedExpression') {
		node = node.expression;
	}
	return node;
};

Node.prototype.findScope = function findScope (functionScope) {
	return this.parent.findScope(functionScope);
};

Node.prototype.getIndentation = function getIndentation () {
	return this.parent.getIndentation();
};

Node.prototype.initialise = function initialise (transforms) {
	for (var i = 0, list = this.keys; i < list.length; i += 1) {
		var key = list[i];

			var value = this[key];

		if (Array.isArray(value)) {
			value.forEach(function (node) { return node && node.initialise(transforms); });
		} else if (value && typeof value === 'object') {
			value.initialise(transforms);
		}
	}
};

Node.prototype.toJSON = function toJSON$1 () {
	return toJSON(this);
};

Node.prototype.toString = function toString () {
	return this.program.magicString.original.slice(this.start, this.end);
};

Node.prototype.transpile = function transpile (code, transforms) {
	for (var i = 0, list = this.keys; i < list.length; i += 1) {
		var key = list[i];

			var value = this[key];

		if (Array.isArray(value)) {
			value.forEach(function (node) { return node && node.transpile(code, transforms); });
		} else if (value && typeof value === 'object') {
			value.transpile(code, transforms);
		}
	}
};

function extractNames(node) {
	var names = [];
	extractors[node.type](names, node);
	return names;
}

var extractors = {
	Identifier: function Identifier(names, node) {
		names.push(node);
	},

	ObjectPattern: function ObjectPattern(names, node) {
		for (var i = 0, list = node.properties; i < list.length; i += 1) {
			var prop = list[i];

			extractors[prop.type](names, prop);
		}
	},

	Property: function Property(names, node) {
		extractors[node.value.type](names, node.value);
	},

	ArrayPattern: function ArrayPattern(names, node) {
		for (var i = 0, list = node.elements; i < list.length; i += 1) {
			var element = list[i];

			if (element) { extractors[element.type](names, element); }
		}
	},

	RestElement: function RestElement(names, node) {
		extractors[node.argument.type](names, node.argument);
	},

	AssignmentPattern: function AssignmentPattern(names, node) {
		extractors[node.left.type](names, node.left);
	}
};

var reserved = Object.create(null);
'do if in for let new try var case else enum eval null this true void with await break catch class const false super throw while yield delete export import public return static switch typeof default extends finally package private continue debugger function arguments interface protected implements instanceof'
	.split(' ')
	.forEach(function (word) { return (reserved[word] = true); });

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
	addDeclaration: function addDeclaration(node, kind) {
		for (var i = 0, list = extractNames(node); i < list.length; i += 1) {
			var identifier = list[i];

			var name = identifier.name;

			var declaration = { name: name, node: identifier, kind: kind, instances: [] };
			this.declarations[name] = declaration;

			if (this.isBlockScope) {
				if (!this.functionScope.blockScopedDeclarations[name])
					{ this.functionScope.blockScopedDeclarations[name] = []; }
				this.functionScope.blockScopedDeclarations[name].push(declaration);
			}
		}
	},

	addReference: function addReference(identifier) {
		if (this.consolidated) {
			this.consolidateReference(identifier);
		} else {
			this.identifiers.push(identifier);
		}
	},

	consolidate: function consolidate() {
		for (var i = 0; i < this.identifiers.length; i += 1) {
			// we might push to the array during consolidation, so don't cache length
			var identifier = this.identifiers[i];
			this.consolidateReference(identifier);
		}

		this.consolidated = true; // TODO understand why this is necessary... seems bad
	},

	consolidateReference: function consolidateReference(identifier) {
		var declaration = this.declarations[identifier.name];
		if (declaration) {
			declaration.instances.push(identifier);
		} else {
			this.references[identifier.name] = true;
			if (this.parent) { this.parent.addReference(identifier); }
		}
	},

	contains: function contains(name) {
		return (
			this.declarations[name] ||
			(this.parent ? this.parent.contains(name) : false)
		);
	},

	createIdentifier: function createIdentifier(base) {
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
			name = base + "$" + (counter++);
		}

		this.aliases[name] = true;
		return name;
	},

	createDeclaration: function createDeclaration(base) {
		var id = this.createIdentifier(base);
		this.createDeclarationCallback(id);
		return id;
	},

	findDeclaration: function findDeclaration(name) {
		return (
			this.declarations[name] ||
			(this.parent && this.parent.findDeclaration(name))
		);
	},

	// Sometimes, block scope declarations change name during transpilation
	resolveName: function resolveName(name) {
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
		.map(function (line, i) { return ((pad(i + first + 1, numDigits)) + " : " + (line.replace(/\t/g, '  '))); })
		.join('\n');

	snippet += '\n' + repeat(' ', numDigits + 3 + offset) + repeat('^', length);

	return snippet;
}

var CompileError = /*@__PURE__*/(function (Error) {
	function CompileError(message, node) {
		Error.call(this, message);

		this.name = 'CompileError';
		if (!node) {
			return;
		}

		var source = node.program.magicString.original;
		var loc = locate(source, node.start);

		this.message = message + " (" + (loc.line) + ":" + (loc.column) + ")";

		this.stack = new Error().stack.replace(
			new RegExp((".+new " + (this.name) + ".+\\n"), 'm'),
			''
		);

		this.loc = loc;
		this.snippet = getSnippet(source, loc, node.end - node.start);
	}

	if ( Error ) CompileError.__proto__ = Error;
	CompileError.prototype = Object.create( Error && Error.prototype );
	CompileError.prototype.constructor = CompileError;

	CompileError.prototype.toString = function toString () {
		return ((this.name) + ": " + (this.message) + "\n" + (this.snippet));
	};

	CompileError.missingTransform = function missingTransform (feature, transformKey, node, dangerousKey) {
		if ( dangerousKey === void 0 ) dangerousKey = null;

		var maybeDangerous = dangerousKey ? (", or `transforms: { " + dangerousKey + ": true }` if you know what you're doing") : '';
		throw new CompileError(("Transforming " + feature + " is not " + (dangerousKey ? "fully supported" : "implemented") + ". Use `transforms: { " + transformKey + ": false }` to skip transformation and disable this error" + maybeDangerous + "."), node);
	};

	return CompileError;
}(Error));

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
	statementGenerators.push(function (start, prefix, suffix) {
		code.overwrite(node.start, node.end, (inline ? prefix : (prefix + "var ")) + resolveName(node) + " = " + ref + suffix);
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
	statementGenerators.push(function (start, prefix, suffix) {
		code.prependRight(node.start, inline ? prefix : (prefix + "var "));
		code.appendLeft(node.end, (" = " + ref + suffix));
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
		statementGenerators.push(function (start, prefix, suffix) {
			code.prependRight(
				node.left.end,
				(prefix + "if ( " + name + " === void 0 ) " + name)
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

	node.elements.forEach(function (element, i) {
		if (!element) { return; }

		if (element.type === 'RestElement') {
			handleProperty(
				code,
				createIdentifier,
				resolveName,
				c,
				element.argument,
				(ref + ".slice(" + i + ")"),
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
				(ref + "[" + i + "]"),
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
	var this$1 = this;

	var c = node.start;

	var nonRestKeys = [];
	node.properties.forEach(function (prop) {
		var value;
		var content;
		if (prop.type === 'Property') {
			content = prop.value;
			if (!prop.computed && prop.key.type === 'Identifier') {
				value = ref + "." + (prop.key.name);
				nonRestKeys.push(("\"" + (prop.key.name) + "\""));
			} else if (!prop.computed && prop.key.type === 'Literal') {
				value = ref + "[" + (prop.key.raw) + "]";
				nonRestKeys.push(JSON.stringify(String(prop.key.value)));
			} else {
				var expr = code.slice(prop.key.start, prop.key.end);
				value = ref + "[" + expr + "]";
				nonRestKeys.push(("String(" + expr + ")"));
			}
		} else if (prop.type === 'RestElement') {
			content = prop.argument;
			value = createIdentifier('rest');
			statementGenerators.push(function (start, prefix, suffix) {
				var helper = prop.program.getObjectWithoutPropertiesHelper(code);
				code.overwrite(
					prop.start,
					(c = prop.argument.start),
					(inline ? prefix : (prefix + "var ")) + value + " = " + helper + "( " + ref + ", [" + (nonRestKeys.join(', ')) + "] )" + suffix
				);
				code.move(prop.start, c, start);
			});
		} else {
			throw new CompileError(
				this$1,
				("Unexpected node of type " + (prop.type) + " in object pattern")
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

			statementGenerators.push(function (start, prefix, suffix) {
				if (inline) {
					code.prependRight(
						node.right.start,
						(name + " = " + value + ", " + name + " = " + name + " === void 0 ? ")
					);
					code.appendLeft(node.right.end, (" : " + name + suffix));
				} else {
					code.prependRight(
						node.right.start,
						(prefix + "var " + name + " = " + value + "; if ( " + name + " === void 0 ) " + name + " = ")
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

				statementGenerators.push(function (start, prefix, suffix) {
					// this feels a tiny bit hacky, but we can't do a
					// straightforward appendLeft and keep correct order...
					code.prependRight(node.start, (inline ? '' : (prefix + "var ")) + ref + " = ");
					code.overwrite(node.start, (c = node.start + 1), value);
					code.appendLeft(c, suffix);

					code.overwrite(
						node.start,
						(c = node.start + 1),
						(inline ? '' : (prefix + "var ")) + ref + " = " + value + suffix
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

				statementGenerators.push(function (start, prefix, suffix) {
					code.prependRight(node.start, (inline ? '' : (prefix + "var ")) + ref$1 + " = ");
					code.overwrite(node.start, (c = node.start + 1), value, {
						contentOnly: true
					});
					code.appendLeft(c, suffix);

					code.move(node.start, c, start);
				});

				node.elements.forEach(function (element, i) {
					if (!element) { return; }

					if (element.type === 'RestElement') {
						handleProperty(
							code,
							createIdentifier,
							resolveName,
							c,
							element.argument,
							(ref$1 + ".slice(" + i + ")"),
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
							(ref$1 + "[" + i + "]"),
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
						(value + ".slice(" + index + ")"),
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
						(value + "[" + index + "]"),
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
			throw new Error(("Unexpected node type in destructuring (" + (node.type) + ")"));
		}
	}
}

function isUseStrict(node) {
	if (!node) { return false; }
	if (node.type !== 'ExpressionStatement') { return false; }
	if (node.expression.type !== 'Literal') { return false; }
	return node.expression.value === 'use strict';
}

var BlockStatement = /*@__PURE__*/(function (Node$$1) {
	function BlockStatement () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) BlockStatement.__proto__ = Node$$1;
	BlockStatement.prototype = Object.create( Node$$1 && Node$$1.prototype );
	BlockStatement.prototype.constructor = BlockStatement;

	BlockStatement.prototype.createScope = function createScope () {
		var this$1 = this;

		this.parentIsFunction = /Function/.test(this.parent.type);
		this.isFunctionBlock = this.parentIsFunction || this.parent.type === 'Root';
		this.scope = new Scope({
			block: !this.isFunctionBlock,
			parent: this.parent.findScope(false),
			declare: function (id) { return this$1.createdDeclarations.push(id); }
		});

		if (this.parentIsFunction) {
			this.parent.params.forEach(function (node) {
				this$1.scope.addDeclaration(node, 'param');
			});
		}
	};

	BlockStatement.prototype.initialise = function initialise (transforms) {
		this.thisAlias = null;
		this.argumentsAlias = null;
		this.defaultParameters = [];
		this.createdDeclarations = [];

		// normally the scope gets created here, during initialisation,
		// but in some cases (e.g. `for` statements), we need to create
		// the scope early, as it pertains to both the init block and
		// the body of the statement
		if (!this.scope) { this.createScope(); }

		this.body.forEach(function (node) { return node.initialise(transforms); });

		this.scope.consolidate();
	};

	BlockStatement.prototype.findLexicalBoundary = function findLexicalBoundary () {
		if (this.type === 'Program') { return this; }
		if (/^Function/.test(this.parent.type)) { return this; }

		return this.parent.findLexicalBoundary();
	};

	BlockStatement.prototype.findScope = function findScope (functionScope) {
		if (functionScope && !this.isFunctionBlock)
			{ return this.parent.findScope(functionScope); }
		return this.scope;
	};

	BlockStatement.prototype.getArgumentsAlias = function getArgumentsAlias () {
		if (!this.argumentsAlias) {
			this.argumentsAlias = this.scope.createIdentifier('arguments');
		}

		return this.argumentsAlias;
	};

	BlockStatement.prototype.getArgumentsArrayAlias = function getArgumentsArrayAlias () {
		if (!this.argumentsArrayAlias) {
			this.argumentsArrayAlias = this.scope.createIdentifier('argsArray');
		}

		return this.argumentsArrayAlias;
	};

	BlockStatement.prototype.getThisAlias = function getThisAlias () {
		if (!this.thisAlias) {
			this.thisAlias = this.scope.createIdentifier('this');
		}

		return this.thisAlias;
	};

	BlockStatement.prototype.getIndentation = function getIndentation () {
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
	};

	BlockStatement.prototype.transpile = function transpile (code, transforms) {
		var this$1 = this;

		var indentation = this.getIndentation();

		var introStatementGenerators = [];

		if (this.argumentsAlias) {
			introStatementGenerators.push(function (start, prefix, suffix) {
				var assignment = prefix + "var " + (this$1.argumentsAlias) + " = arguments" + suffix;
				code.appendLeft(start, assignment);
			});
		}

		if (this.thisAlias) {
			introStatementGenerators.push(function (start, prefix, suffix) {
				var assignment = prefix + "var " + (this$1.thisAlias) + " = this" + suffix;
				code.appendLeft(start, assignment);
			});
		}

		if (this.argumentsArrayAlias) {
			introStatementGenerators.push(function (start, prefix, suffix) {
				var i = this$1.scope.createIdentifier('i');
				var assignment = prefix + "var " + i + " = arguments.length, " + (this$1.argumentsArrayAlias) + " = Array(" + i + ");\n" + indentation + "while ( " + i + "-- ) " + (this$1.argumentsArrayAlias) + "[" + i + "] = arguments[" + i + "]" + suffix;
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

		Node$$1.prototype.transpile.call(this, code, transforms);

		if (this.createdDeclarations.length) {
			introStatementGenerators.push(function (start, prefix, suffix) {
				var assignment = prefix + "var " + (this$1.createdDeclarations.join(', ')) + suffix;
				code.appendLeft(start, assignment);
			});
		}

		if (this.synthetic) {
			if (this.parent.type === 'ArrowFunctionExpression') {
				var expr = this.body[0];

				if (introStatementGenerators.length) {
					code
						.appendLeft(this.start, "{")
						.prependRight(this.end, ((this.parent.getIndentation()) + "}"));

					code.prependRight(expr.start, ("\n" + indentation + "return "));
					code.appendLeft(expr.end, ";\n");
				} else if (transforms.arrow) {
					code.prependRight(expr.start, "{ return ");
					code.appendLeft(expr.end, "; }");
				}
			} else if (introStatementGenerators.length) {
				code.prependRight(this.start, "{").appendLeft(this.end, "}");
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

		var prefix = "\n" + indentation;
		var suffix = ';';
		introStatementGenerators.forEach(function (fn, i) {
			if (i === introStatementGenerators.length - 1) { suffix = ";\n"; }
			fn(start, prefix, suffix);
		});
	};

	BlockStatement.prototype.transpileParameters = function transpileParameters (params, code, transforms, indentation, introStatementGenerators) {
		var this$1 = this;

		params.forEach(function (param) {
			if (
				param.type === 'AssignmentPattern' &&
				param.left.type === 'Identifier'
			) {
				if (transforms.defaultParameter) {
					introStatementGenerators.push(function (start, prefix, suffix) {
						var lhs = prefix + "if ( " + (param.left.name) + " === void 0 ) " + (param.left.name);

						code
							.prependRight(param.left.end, lhs)
							.move(param.left.end, param.right.end, start)
							.appendLeft(param.right.end, suffix);
					});
				}
			} else if (param.type === 'RestElement') {
				if (transforms.spreadRest) {
					introStatementGenerators.push(function (start, prefix, suffix) {
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
						var len = this$1.scope.createIdentifier('len');
						var count = params.length - 1;

						if (count) {
							code.prependRight(
								start,
								(prefix + "var " + name + " = [], " + len + " = arguments.length - " + count + ";\n" + indentation + "while ( " + len + "-- > 0 ) " + name + "[ " + len + " ] = arguments[ " + len + " + " + count + " ]" + suffix)
							);
						} else {
							code.prependRight(
								start,
								(prefix + "var " + name + " = [], " + len + " = arguments.length;\n" + indentation + "while ( " + len + "-- ) " + name + "[ " + len + " ] = arguments[ " + len + " ]" + suffix)
							);
						}
					});
				}
			} else if (param.type !== 'Identifier') {
				if (transforms.parameterDestructuring) {
					var ref = this$1.scope.createIdentifier('ref');
					destructure(
						code,
						function (id) { return this$1.scope.createIdentifier(id); },
						function (ref) {
							var name = ref.name;

							return this$1.scope.resolveName(name);
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
	};

	BlockStatement.prototype.transpileBlockScopedIdentifiers = function transpileBlockScopedIdentifiers (code) {
		var this$1 = this;

		Object.keys(this.scope.blockScopedDeclarations).forEach(function (name) {
			var declarations = this$1.scope.blockScopedDeclarations[name];

			for (var i$2 = 0, list$2 = declarations; i$2 < list$2.length; i$2 += 1) {
				var declaration = list$2[i$2];

				var cont = false; // TODO implement proper continue...

				if (declaration.kind === 'for.let') {
					// special case
					var forStatement = declaration.node.findNearest('ForStatement');

					if (forStatement.shouldRewriteAsFunction) {
						var outerAlias = this$1.scope.createIdentifier(name);
						var innerAlias = forStatement.reassigned[name]
							? this$1.scope.createIdentifier(name)
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
					var alias$1 = this$1.scope.createIdentifier(name);

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
	};

	return BlockStatement;
}(Node));

var hasDashes = function (val) { return /-/.test(val); };

var formatKey = function (key) { return (hasDashes(key) ? ("'" + key + "'") : key); };

var formatVal = function (val) { return (val ? '' : 'true'); };

var JSXAttribute = /*@__PURE__*/(function (Node$$1) {
	function JSXAttribute () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXAttribute.__proto__ = Node$$1;
	JSXAttribute.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXAttribute.prototype.constructor = JSXAttribute;

	JSXAttribute.prototype.transpile = function transpile (code, transforms) {
		var ref = this.name;
		var start = ref.start;
		var name = ref.name;

		// Overwrite equals sign if value is present.
		var end = this.value ? this.value.start : this.name.end;

		code.overwrite(start, end, ((formatKey(name)) + ": " + (formatVal(this.value))));

		Node$$1.prototype.transpile.call(this, code, transforms);
	};

	return JSXAttribute;
}(Node));

function containsNewLine(node) {
	return (
		node.type === 'JSXText' && !/\S/.test(node.value) && /\n/.test(node.value)
	);
}

var JSXClosingElement = /*@__PURE__*/(function (Node$$1) {
	function JSXClosingElement () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXClosingElement.__proto__ = Node$$1;
	JSXClosingElement.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXClosingElement.prototype.constructor = JSXClosingElement;

	JSXClosingElement.prototype.transpile = function transpile (code) {
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
	};

	return JSXClosingElement;
}(Node));

function containsNewLine$1(node) {
	return (
		node.type === 'JSXText' && !/\S/.test(node.value) && /\n/.test(node.value)
	);
}

var JSXClosingFragment = /*@__PURE__*/(function (Node$$1) {
	function JSXClosingFragment () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXClosingFragment.__proto__ = Node$$1;
	JSXClosingFragment.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXClosingFragment.prototype.constructor = JSXClosingFragment;

	JSXClosingFragment.prototype.transpile = function transpile (code) {
		var spaceBeforeParen = true;

		var lastChild = this.parent.children[this.parent.children.length - 1];

		// omit space before closing paren if this is on a separate line
		if (lastChild && containsNewLine$1(lastChild)) {
			spaceBeforeParen = false;
		}

		code.overwrite(this.start, this.end, spaceBeforeParen ? ' )' : ')');
	};

	return JSXClosingFragment;
}(Node));

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

var JSXElement = /*@__PURE__*/(function (Node$$1) {
	function JSXElement () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXElement.__proto__ = Node$$1;
	JSXElement.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXElement.prototype.constructor = JSXElement;

	JSXElement.prototype.transpile = function transpile (code, transforms) {
		Node$$1.prototype.transpile.call(this, code, transforms);

		var children = this.children.filter(function (child) {
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
					code.appendLeft(c, ("," + tail));
				}

				if (child.type === 'JSXText') {
					var str = normalise(child.value, i === children.length - 1);
					code.overwrite(child.start, child.end, str);
				}

				c = child.end;
			}
		}
	};

	return JSXElement;
}(Node));

var JSXExpressionContainer = /*@__PURE__*/(function (Node$$1) {
	function JSXExpressionContainer () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXExpressionContainer.__proto__ = Node$$1;
	JSXExpressionContainer.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXExpressionContainer.prototype.constructor = JSXExpressionContainer;

	JSXExpressionContainer.prototype.transpile = function transpile (code, transforms) {
		code.remove(this.start, this.expression.start);
		code.remove(this.expression.end, this.end);

		Node$$1.prototype.transpile.call(this, code, transforms);
	};

	return JSXExpressionContainer;
}(Node));

var JSXFragment = /*@__PURE__*/(function (JSXElement$$1) {
	function JSXFragment () {
		JSXElement$$1.apply(this, arguments);
	}if ( JSXElement$$1 ) JSXFragment.__proto__ = JSXElement$$1;
	JSXFragment.prototype = Object.create( JSXElement$$1 && JSXElement$$1.prototype );
	JSXFragment.prototype.constructor = JSXFragment;

	

	return JSXFragment;
}(JSXElement));

var JSXOpeningElement = /*@__PURE__*/(function (Node$$1) {
	function JSXOpeningElement () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXOpeningElement.__proto__ = Node$$1;
	JSXOpeningElement.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXOpeningElement.prototype.constructor = JSXOpeningElement;

	JSXOpeningElement.prototype.transpile = function transpile (code, transforms) {
		Node$$1.prototype.transpile.call(this, code, transforms);

		code.overwrite(this.start, this.name.start, ((this.program.jsx) + "( "));

		var html =
			this.name.type === 'JSXIdentifier' &&
			this.name.name[0] === this.name.name[0].toLowerCase();
		if (html) { code.prependRight(this.name.start, "'"); }

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
					before = html ? "'," : ',';
				} else {
					if (!this.program.options.objectAssign) {
						throw new CompileError(
							"Mixed JSX attributes ending in spread requires specified objectAssign option with 'Object.assign' or polyfill helper.",
							this
						);
					}
					before = html
						? ("', " + (this.program.options.objectAssign) + "({},")
						: (", " + (this.program.options.objectAssign) + "({},");
					after = ')';
				}
			} else {
				before = html ? "', {" : ', {';
				after = ' }';
			}

			code.prependRight(this.name.end, before);

			if (after) {
				code.appendLeft(this.attributes[len - 1].end, after);
			}
		} else {
			code.appendLeft(this.name.end, html ? "', null" : ", null");
			c = this.name.end;
		}

		if (this.selfClosing) {
			code.overwrite(c, this.end, this.attributes.length ? ")" : " )");
		} else {
			code.remove(c, this.end);
		}
	};

	return JSXOpeningElement;
}(Node));

var JSXOpeningFragment = /*@__PURE__*/(function (Node$$1) {
	function JSXOpeningFragment () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXOpeningFragment.__proto__ = Node$$1;
	JSXOpeningFragment.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXOpeningFragment.prototype.constructor = JSXOpeningFragment;

	JSXOpeningFragment.prototype.transpile = function transpile (code) {
		code.overwrite(this.start, this.end, ((this.program.jsx) + "( " + (this.program.jsxFragment) + ", null"));
	};

	return JSXOpeningFragment;
}(Node));

var JSXSpreadAttribute = /*@__PURE__*/(function (Node$$1) {
	function JSXSpreadAttribute () {
		Node$$1.apply(this, arguments);
	}

	if ( Node$$1 ) JSXSpreadAttribute.__proto__ = Node$$1;
	JSXSpreadAttribute.prototype = Object.create( Node$$1 && Node$$1.prototype );
	JSXSpreadAttribute.prototype.constructor = JSXSpreadAttribute;

	JSXSpreadAttribute.prototype.transpile = function transpile (code, transforms) {
		code.remove(this.start, this.argument.start);
		code.remove(this.argument.end, this.end);

		Node$$1.prototype.transpile.call(this, code, transforms);
	};

	return JSXSpreadAttribute;
}(Node));

var types = {
	JSXAttribute: JSXAttribute,
	JSXClosingElement: JSXClosingElement,
	JSXClosingFragment: JSXClosingFragment,
	JSXElement: JSXElement,
	JSXExpressionContainer: JSXExpressionContainer,
	JSXFragment: JSXFragment,
	JSXOpeningElement: JSXOpeningElement,
	JSXOpeningFragment: JSXOpeningFragment,
	JSXSpreadAttribute: JSXSpreadAttribute,
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
			function (key) { return typeof raw[key] === 'object'; }
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
	export: function export$1(options) {
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

	findNearest: function findNearest() {
		return null;
	},

	findScope: function findScope() {
		return null;
	},

	getObjectWithoutPropertiesHelper: function getObjectWithoutPropertiesHelper(code) {
		if (!this.objectWithoutPropertiesHelper) {
			this.objectWithoutPropertiesHelper = this.body.scope.createIdentifier('objectWithoutProperties');
			code.prependLeft(this.prependAt, "function " + (this.objectWithoutPropertiesHelper) + " (obj, exclude) { " +
				"var target = {}; for (var k in obj) " +
				"if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) " +
				"target[k] = obj[k]; return target; }\n"
			);
		}
		return this.objectWithoutPropertiesHelper;
	}
};

var matrix = {
	chrome: {
		    48: 610719,
		    49: 652287,
		    50: 783359,
		    51: 783359,
		    52: 1045503,
		    53: 1045503,
		    54: 1045503,
		    55: 3142655,
		    56: 3142655,
		    57: 3142655,
		    58: 4191231,
		    59: 4191231,
		    60: 8385535,
		    61: 8385535,
		    62: 8385535,
		    63: 8385535,
		    64: 8385535,
		    65: 8385535,
		    66: 8385535,
		    67: 8385535,
		    68: 8385535,
		    69: 8385535,
		    70: 8385535,
		    71: 8385535
	},
	firefox: {
		    43: 643515,
		    44: 643515,
		    45: 643519,
		    46: 774591,
		    47: 774655,
		    48: 774655,
		    49: 774655,
		    50: 774655,
		    51: 775167,
		    52: 4191231,
		    53: 4191231,
		    54: 4191231,
		    55: 8385535,
		    56: 8385535,
		    57: 8385535,
		    58: 8385535,
		    59: 8385535,
		    60: 8385535,
		    61: 8385535,
		    62: 8385535,
		    63: 8385535,
		    64: 8385535
	},
	safari: {
		     8: 524297,
		     9: 594141,
		    10: 1831935,
		'10.1': 4191231,
		    11: 4191231,
		'11.1': 8385535,
		    12: 8385535
	},
	ie: {
		     8: 0,
		     9: 524289,
		    10: 524289,
		    11: 524289 // no let/const in for loops
	},
	edge: {
		    12: 610459,
		    13: 774559,
		    14: 2085887,
		    15: 4183039,
		    16: 4183039,
		    17: 4183039,
		    18: 4183039,
		    19: 4183039
	},
	node: {
		'0.10': 524289,
		'0.12': 524417,
		     4: 594335,
		     5: 594335,
		     6: 783359,
		     8: 4191231,
		 '8.3': 8385535,
		 '8.7': 8385535,
		'8.10': 8385535
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

var parser = acorn.Parser.extend(acornDynamicImport, acornJsx());

var dangerousTransforms = ['dangerousTaggedTemplateString', 'dangerousForOf'];

function target(target) {
	var targets = Object.keys(target);
	var bitmask = targets.length
		? 8388607
		: 524289;

	Object.keys(target).forEach(function (environment) {
		var versions = matrix[environment];
		if (!versions)
			{ throw new Error(
				("Unknown environment '" + environment + "'. Please raise an issue at https://github.com/bublejs/buble/issues")
			); }

		var targetVersion = target[environment];
		if (!(targetVersion in versions))
			{ throw new Error(
				("Support data exists for the following versions of " + environment + ": " + (Object.keys(
					versions
				).join(
					', '
				)) + ". Please raise an issue at https://github.com/bublejs/buble/issues")
			); }
		var support = versions[targetVersion];

		bitmask &= support;
	});

	var transforms = Object.create(null);
	features.forEach(function (name, i) {
		transforms[name] = !(bitmask & (1 << i));
	});

	dangerousTransforms.forEach(function (name) {
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
			onComment: function (block, text) {
				if (!jsx) {
					var match = /@jsx\s+([^\s]+)/.exec(text);
					if (match) { jsx = match[1]; }
				}
			}
		});
		options.jsx = jsx || options.jsx;
	} catch (err) {
		err.snippet = getSnippet(source, err.loc);
		err.toString = function () { return ((err.name) + ": " + (err.message) + "\n" + (err.snippet)); };
		throw err;
	}

	var transforms = target(options.target || {});
	Object.keys(options.transforms || {}).forEach(function (name) {
		if (name === 'modules') {
			if (!('moduleImport' in options.transforms))
				{ transforms.moduleImport = options.transforms.modules; }
			if (!('moduleExport' in options.transforms))
				{ transforms.moduleExport = options.transforms.modules; }
			return;
		}

		if (!(name in transforms)) { throw new Error(("Unknown transform '" + name + "'")); }
		transforms[name] = options.transforms[name];
	});
	if (options.objectAssign === true) { options.objectAssign = 'Object.assign'; }
	return new Program(source, ast, transforms, options).export(options);
}

exports.target = target;
exports.transform = transform;
exports.VERSION = version;
//# sourceMappingURL=buble-browser.cjs.js.map
