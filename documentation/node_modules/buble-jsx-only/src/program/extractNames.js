export default function extractNames(node) {
	const names = [];
	extractors[node.type](names, node);
	return names;
}

const extractors = {
	Identifier(names, node) {
		names.push(node);
	},

	ObjectPattern(names, node) {
		for (const prop of node.properties) {
			extractors[prop.type](names, prop);
		}
	},

	Property(names, node) {
		extractors[node.value.type](names, node.value);
	},

	ArrayPattern(names, node) {
		for (const element of node.elements) {
			if (element) extractors[element.type](names, element);
		}
	},

	RestElement(names, node) {
		extractors[node.argument.type](names, node.argument);
	},

	AssignmentPattern(names, node) {
		extractors[node.left.type](names, node.left);
	}
};
