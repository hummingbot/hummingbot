import Node from '../Node.js';

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

export default class JSXElement extends Node {
	transpile(code, transforms) {
		super.transpile(code, transforms);

		const children = this.children.filter(child => {
			if (child.type !== 'JSXText') return true;

			// remove whitespace-only literals, unless on a single line
			return /\S/.test(child.raw) || !/\n/.test(child.raw);
		});

		if (children.length) {
			let c = (this.openingElement || this.openingFragment).end;

			let i;
			for (i = 0; i < children.length; i += 1) {
				const child = children[i];

				if (
					child.type === 'JSXExpressionContainer' &&
					child.expression.type === 'JSXEmptyExpression'
				) {
					// empty block is a no op
				} else {
					const tail =
						code.original[c] === '\n' && child.type !== 'JSXText' ? '' : ' ';
					code.appendLeft(c, `,${tail}`);
				}

				if (child.type === 'JSXText') {
					const str = normalise(child.value, i === children.length - 1);
					code.overwrite(child.start, child.end, str);
				}

				c = child.end;
			}
		}
	}
}
