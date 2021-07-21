import Node from '../Node.js';

export default class JSXSpreadAttribute extends Node {
	transpile(code, transforms) {
		code.remove(this.start, this.argument.start);
		code.remove(this.argument.end, this.end);

		super.transpile(code, transforms);
	}
}
