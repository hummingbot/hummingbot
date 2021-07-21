import Node from '../../Node.js';

export default class LoopStatement extends Node {
	findScope(functionScope) {
		return functionScope || !this.createdScope
			? this.parent.findScope(functionScope)
			: this.body.scope;
	}

	initialise(transforms) {
		this.body.createScope();
		this.createdScope = true;

		// this is populated as and when reassignments occur
		this.reassigned = Object.create(null);
		this.aliases = Object.create(null);

		this.thisRefs = [];

		super.initialise(transforms);

		if (transforms.letConst) {
			// see if any block-scoped declarations are referenced
			// inside function expressions
			const names = Object.keys(this.body.scope.declarations);

			let i = names.length;
			while (i--) {
				const name = names[i];
				const declaration = this.body.scope.declarations[name];

				let j = declaration.instances.length;
				while (j--) {
					const instance = declaration.instances[j];
					const nearestFunctionExpression = instance.findNearest(/Function/);

					if (
						nearestFunctionExpression &&
						nearestFunctionExpression.depth > this.depth
					) {
						this.shouldRewriteAsFunction = true;
						for (const node of this.thisRefs) {
							node.alias = node.alias || node.findLexicalBoundary().getThisAlias();
						}
						break;
					}
				}

				if (this.shouldRewriteAsFunction) break;
			}
		}
	}

	transpile(code, transforms) {
		const needsBlock =
			this.type != 'ForOfStatement' &&
			(this.body.type !== 'BlockStatement' ||
				(this.body.type === 'BlockStatement' && this.body.synthetic));

		if (this.shouldRewriteAsFunction) {
			const i0 = this.getIndentation();
			const i1 = i0 + code.getIndentString();

			const argString = this.args ? ` ${this.args.join(', ')} ` : '';
			const paramString = this.params ? ` ${this.params.join(', ')} ` : '';

			const functionScope = this.findScope(true);
			const loop = functionScope.createIdentifier('loop');

			const before =
				`var ${loop} = function (${paramString}) ` +
				(this.body.synthetic ? `{\n${i0}${code.getIndentString()}` : '');
			const after = (this.body.synthetic ? `\n${i0}}` : '') + `;\n\n${i0}`;

			code.prependRight(this.body.start, before);
			code.appendLeft(this.body.end, after);
			code.move(this.start, this.body.start, this.body.end);

			if (this.canBreak || this.canReturn) {
				const returned = functionScope.createIdentifier('returned');

				let insert = `{\n${i1}var ${returned} = ${loop}(${argString});\n`;
				if (this.canBreak)
					insert += `\n${i1}if ( ${returned} === 'break' ) break;`;
				if (this.canReturn)
					insert += `\n${i1}if ( ${returned} ) return ${returned}.v;`;
				insert += `\n${i0}}`;

				code.prependRight(this.body.end, insert);
			} else {
				const callExpression = `${loop}(${argString});`;

				if (this.type === 'DoWhileStatement') {
					code.overwrite(
						this.start,
						this.body.start,
						`do {\n${i1}${callExpression}\n${i0}}`
					);
				} else {
					code.prependRight(this.body.end, callExpression);
				}
			}
		} else if (needsBlock) {
			code.appendLeft(this.body.start, '{ ');
			code.prependRight(this.body.end, ' }');
		}

		super.transpile(code, transforms);
	}
}
