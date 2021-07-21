// used for debugging, without the noise created by
// circular references
function toJSON(node) {
	const obj = {};

	Object.keys(node).forEach(key => {
		if (
			key === 'parent' ||
			key === 'program' ||
			key === 'keys' ||
			key === '__wrapped'
		)
			return;

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

export default class Node {
	ancestor(level) {
		let node = this;
		while (level--) {
			node = node.parent;
			if (!node) return null;
		}

		return node;
	}

	contains(node) {
		while (node) {
			if (node === this) return true;
			node = node.parent;
		}

		return false;
	}

	findLexicalBoundary() {
		return this.parent.findLexicalBoundary();
	}

	findNearest(type) {
		if (typeof type === 'string') type = new RegExp(`^${type}$`);
		if (type.test(this.type)) return this;
		return this.parent.findNearest(type);
	}

	unparenthesizedParent() {
		let node = this.parent;
		while (node && node.type === 'ParenthesizedExpression') {
			node = node.parent;
		}
		return node;
	}

	unparenthesize() {
		let node = this;
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
		for (const key of this.keys) {
			const value = this[key];

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
		for (const key of this.keys) {
			const value = this[key];

			if (Array.isArray(value)) {
				value.forEach(node => node && node.transpile(code, transforms));
			} else if (value && typeof value === 'object') {
				value.transpile(code, transforms);
			}
		}
	}
}
