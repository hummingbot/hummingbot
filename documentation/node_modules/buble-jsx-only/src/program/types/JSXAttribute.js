import Node from '../Node.js';

const hasDashes = val => /-/.test(val);

const formatKey = key => (hasDashes(key) ? `'${key}'` : key);

const formatVal = val => (val ? '' : 'true');

export default class JSXAttribute extends Node {
	transpile(code, transforms) {
		const { start, name } = this.name;

		// Overwrite equals sign if value is present.
		const end = this.value ? this.value.start : this.name.end;

		code.overwrite(start, end, `${formatKey(name)}: ${formatVal(this.value)}`);

		super.transpile(code, transforms);
	}
}
