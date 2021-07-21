export default function isReference(node, parent) {
	if (node.type === 'MemberExpression') {
		return !node.computed && isReference(node.object, node);
	}

	if (node.type === 'Identifier') {
		// the only time we could have an identifier node without a parent is
		// if it's the entire body of a function without a block statement –
		// i.e. an arrow function expression like `a => a`
		if (!parent) return true;

		if (/(Function|Class)Expression/.test(parent.type)) return false;

		if (parent.type === 'VariableDeclarator') return node === parent.init;

		// TODO is this right?
		if (
			parent.type === 'MemberExpression' ||
			parent.type === 'MethodDefinition'
		) {
			return parent.computed || node === parent.object;
		}

		if (parent.type === 'ArrayPattern') return false;

		// disregard the `bar` in `{ bar: foo }`, but keep it in `{ [bar]: foo }`
		if (parent.type === 'Property') {
			if (parent.parent.type === 'ObjectPattern') return false;
			return parent.computed || node === parent.value;
		}

		// disregard the `bar` in `class Foo { bar () {...} }`
		if (parent.type === 'MethodDefinition') return false;

		// disregard the `bar` in `export { foo as bar }`
		if (parent.type === 'ExportSpecifier' && node !== parent.local)
			return false;

		return true;
	}
}
