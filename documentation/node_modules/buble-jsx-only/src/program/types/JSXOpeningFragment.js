import Node from '../Node.js';

export default class JSXOpeningFragment extends Node {
	transpile(code) {
		code.overwrite(this.start, this.end, `${this.program.jsx}( ${this.program.jsxFragment}, null`);
	}
}
