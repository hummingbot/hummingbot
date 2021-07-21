import MagicString from 'magic-string';
import { createFilter } from 'rollup-pluginutils';

function escape(str) {
	return str.replace(/[-[\]/{}()*+?.\\^$|]/g, '\\$&');
}

function ensureFunction(functionOrValue) {
	if (typeof functionOrValue === 'function') return functionOrValue;
	return () => functionOrValue;
}

function longest(a, b) {
	return b.length - a.length;
}

function getReplacements(options) {
	if (options.values) {
		return Object.assign({}, options.values);
	} else {
		const values = Object.assign({}, options);
		delete values.delimiters;
		delete values.include;
		delete values.exclude;
		delete values.sourcemap;
		delete values.sourceMap;
		return values;
	}
}

function mapToFunctions(object) {
	return Object.keys(object).reduce((functions, key) => {
		functions[key] = ensureFunction(object[key]);
		return functions;
	}, {});
}

export default function replace(options = {}) {
	const filter = createFilter(options.include, options.exclude);
	const { delimiters } = options;
	const functionValues = mapToFunctions(getReplacements(options));
	const keys = Object.keys(functionValues)
		.sort(longest)
		.map(escape);

	const pattern = delimiters
		? new RegExp(`${escape(delimiters[0])}(${keys.join('|')})${escape(delimiters[1])}`, 'g')
		: new RegExp(`\\b(${keys.join('|')})\\b`, 'g');

	return {
		name: 'replace',

		transform(code, id) {
			if (!filter(id)) return null;

			const magicString = new MagicString(code);

			let hasReplacements = false;
			let match;
			let start;
			let end;
			let replacement;

			while ((match = pattern.exec(code))) {
				hasReplacements = true;

				start = match.index;
				end = start + match[0].length;
				replacement = String(functionValues[match[1]](id));

				magicString.overwrite(start, end, replacement);
			}

			if (!hasReplacements) return null;

			const result = { code: magicString.toString() };
			if (options.sourceMap !== false && options.sourcemap !== false)
				result.map = magicString.generateMap({ hires: true });

			return result;
		}
	};
}
