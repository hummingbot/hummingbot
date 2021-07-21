import Node from '../Node.js';
import CompileError from '../../utils/CompileError.js';

export default class JSXOpeningElement extends Node {
	transpile(code, transforms) {
		super.transpile(code, transforms);

		code.overwrite(this.start, this.name.start, `${this.program.jsx}( `);

		const html =
			this.name.type === 'JSXIdentifier' &&
			this.name.name[0] === this.name.name[0].toLowerCase();
		if (html) code.prependRight(this.name.start, `'`);

		const len = this.attributes.length;
		let c = this.name.end;

		if (len) {
			let i;

			let hasSpread = false;
			for (i = 0; i < len; i += 1) {
				if (this.attributes[i].type === 'JSXSpreadAttribute') {
					hasSpread = true;
					break;
				}
			}

			c = this.attributes[0].end;

			for (i = 0; i < len; i += 1) {
				const attr = this.attributes[i];

				if (i > 0) {
					if (attr.start === c) code.prependRight(c, ', ');
					else code.overwrite(c, attr.start, ', ');
				}

				if (hasSpread && attr.type !== 'JSXSpreadAttribute') {
					const lastAttr = this.attributes[i - 1];
					const nextAttr = this.attributes[i + 1];

					if (!lastAttr || lastAttr.type === 'JSXSpreadAttribute') {
						code.prependRight(attr.start, '{ ');
					}

					if (!nextAttr || nextAttr.type === 'JSXSpreadAttribute') {
						code.appendLeft(attr.end, ' }');
					}
				}

				c = attr.end;
			}

			let after;
			let before;
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
