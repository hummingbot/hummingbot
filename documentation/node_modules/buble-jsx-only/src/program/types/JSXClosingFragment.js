import Node from '../Node.js';

function containsNewLine(node) {
	return (
		node.type === 'JSXText' && !/\S/.test(node.value) && /\n/.test(node.value)
	);
}

export default class JSXClosingFragment extends Node {
	transpile(code) {
		let spaceBeforeParen = true;

		const lastChild = this.parent.children[this.parent.children.length - 1];

		// omit space before closing paren if this is on a separate line
		if (lastChild && containsNewLine(lastChild)) {
			spaceBeforeParen = false;
		}

		code.overwrite(this.start, this.end, spaceBeforeParen ? ' )' : ')');
	}
}
