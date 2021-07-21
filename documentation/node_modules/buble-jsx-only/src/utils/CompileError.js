import locate from './locate.js';
import getSnippet from './getSnippet.js';

export default class CompileError extends Error {
	constructor(message, node) {
		super(message);

		this.name = 'CompileError';
		if (!node) {
			return;
		}

		const source = node.program.magicString.original;
		const loc = locate(source, node.start);

		this.message = message + ` (${loc.line}:${loc.column})`;

		this.stack = new Error().stack.replace(
			new RegExp(`.+new ${this.name}.+\\n`, 'm'),
			''
		);

		this.loc = loc;
		this.snippet = getSnippet(source, loc, node.end - node.start);
	}

	toString() {
		return `${this.name}: ${this.message}\n${this.snippet}`;
	}

	static missingTransform(feature, transformKey, node, dangerousKey = null) {
		const maybeDangerous = dangerousKey ? `, or \`transforms: { ${dangerousKey}: true }\` if you know what you're doing` : '';
		throw new CompileError(`Transforming ${feature} is not ${dangerousKey ? "fully supported" : "implemented"}. Use \`transforms: { ${transformKey}: false }\` to skip transformation and disable this error${maybeDangerous}.`, node);
	}
}
