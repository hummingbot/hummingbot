import Node from './Node.js';
import Scope from './Scope.js';
import destructure from '../utils/destructure.js';

function isUseStrict(node) {
	if (!node) return false;
	if (node.type !== 'ExpressionStatement') return false;
	if (node.expression.type !== 'Literal') return false;
	return node.expression.value === 'use strict';
}

export default class BlockStatement extends Node {
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
		if (!this.scope) this.createScope();

		this.body.forEach(node => node.initialise(transforms));

		this.scope.consolidate();
	}

	findLexicalBoundary() {
		if (this.type === 'Program') return this;
		if (/^Function/.test(this.parent.type)) return this;

		return this.parent.findLexicalBoundary();
	}

	findScope(functionScope) {
		if (functionScope && !this.isFunctionBlock)
			return this.parent.findScope(functionScope);
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
			const source = this.program.magicString.original;

			const useOuter = this.synthetic || !this.body.length;
			let c = useOuter ? this.start : this.body[0].start;

			while (c && source[c] !== '\n') c -= 1;

			this.indentation = '';

			// eslint-disable-next-line no-constant-condition
			while (true) {
				c += 1;
				const char = source[c];

				if (char !== ' ' && char !== '\t') break;

				this.indentation += char;
			}

			const indentString = this.program.magicString.getIndentString();

			// account for dedented class constructors
			let parent = this.parent;
			while (parent) {
				if (parent.kind === 'constructor' && !parent.parent.parent.superClass) {
					this.indentation = this.indentation.replace(indentString, '');
				}

				parent = parent.parent;
			}

			if (useOuter) this.indentation += indentString;
		}

		return this.indentation;
	}

	transpile(code, transforms) {
		const indentation = this.getIndentation();

		const introStatementGenerators = [];

		if (this.argumentsAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				const assignment = `${prefix}var ${this.argumentsAlias} = arguments${
					suffix
				}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.thisAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				const assignment = `${prefix}var ${this.thisAlias} = this${suffix}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.argumentsArrayAlias) {
			introStatementGenerators.push((start, prefix, suffix) => {
				const i = this.scope.createIdentifier('i');
				const assignment = `${prefix}var ${i} = arguments.length, ${
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
				const assignment = `${prefix}var ${this.createdDeclarations.join(', ')}${suffix}`;
				code.appendLeft(start, assignment);
			});
		}

		if (this.synthetic) {
			if (this.parent.type === 'ArrowFunctionExpression') {
				const expr = this.body[0];

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

		let start;
		if (isUseStrict(this.body[0])) {
			start = this.body[0].end;
		} else if (this.synthetic || this.parent.type === 'Root') {
			start = this.start;
		} else {
			start = this.start + 1;
		}

		const prefix = `\n${indentation}`;
		let suffix = ';';
		introStatementGenerators.forEach((fn, i) => {
			if (i === introStatementGenerators.length - 1) suffix = `;\n`;
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
						const lhs = `${prefix}if ( ${param.left.name} === void 0 ) ${
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
						const penultimateParam = params[params.length - 2];

						if (penultimateParam) {
							code.remove(
								penultimateParam ? penultimateParam.end : param.start,
								param.end
							);
						} else {
							let start = param.start,
								end = param.end; // TODO https://gitlab.com/Rich-Harris/buble/issues/8

							while (/\s/.test(code.original[start - 1])) start -= 1;
							while (/\s/.test(code.original[end])) end += 1;

							code.remove(start, end);
						}

						const name = param.argument.name;
						const len = this.scope.createIdentifier('len');
						const count = params.length - 1;

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
					const ref = this.scope.createIdentifier('ref');
					destructure(
						code,
						id => this.scope.createIdentifier(id),
						({ name }) => this.scope.resolveName(name),
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
			const declarations = this.scope.blockScopedDeclarations[name];

			for (const declaration of declarations) {
				let cont = false; // TODO implement proper continue...

				if (declaration.kind === 'for.let') {
					// special case
					const forStatement = declaration.node.findNearest('ForStatement');

					if (forStatement.shouldRewriteAsFunction) {
						const outerAlias = this.scope.createIdentifier(name);
						const innerAlias = forStatement.reassigned[name]
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

						for (const identifier of declaration.instances) {
							const alias = forStatement.body.contains(identifier)
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
					const alias = this.scope.createIdentifier(name);

					if (name !== alias) {
						declaration.name = alias;
						code.overwrite(
							declaration.node.start,
							declaration.node.end,
							alias,
							{ storeName: true }
						);

						for (const identifier of declaration.instances) {
							identifier.rewritten = true;
							code.overwrite(identifier.start, identifier.end, alias, {
								storeName: true
							});
						}
					}
				}
			}
		});
	}
}
