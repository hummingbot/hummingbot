import { Parser } from 'acorn';
import acornJsx from 'acorn-jsx';
import acornDynamicImport from 'acorn-dynamic-import';
import Program from './program/Program.js';
import { features, matrix } from './support.js';
import getSnippet from './utils/getSnippet.js';

const parser = Parser.extend(acornDynamicImport, acornJsx());

const dangerousTransforms = ['dangerousTaggedTemplateString', 'dangerousForOf'];

export function target(target) {
	const targets = Object.keys(target);
	let bitmask = targets.length
		? 0b11111111111111111111111
		: 0b00010000000000000000001;

	Object.keys(target).forEach(environment => {
		const versions = matrix[environment];
		if (!versions)
			throw new Error(
				`Unknown environment '${environment}'. Please raise an issue at https://github.com/bublejs/buble/issues`
			);

		const targetVersion = target[environment];
		if (!(targetVersion in versions))
			throw new Error(
				`Support data exists for the following versions of ${environment}: ${Object.keys(
					versions
				).join(
					', '
				)}. Please raise an issue at https://github.com/bublejs/buble/issues`
			);
		const support = versions[targetVersion];

		bitmask &= support;
	});

	const transforms = Object.create(null);
	features.forEach((name, i) => {
		transforms[name] = !(bitmask & (1 << i));
	});

	dangerousTransforms.forEach(name => {
		transforms[name] = false;
	});

	return transforms;
}

export function transform(source, options = {}) {
	let ast;
	let jsx = null;

	try {
		ast = parser.parse(source, {
			ecmaVersion: 10,
			preserveParens: true,
			sourceType: 'module',
			allowAwaitOutsideFunction: true,
			allowReturnOutsideFunction: true,
			allowHashBang: true,
			onComment: (block, text) => {
				if (!jsx) {
					const match = /@jsx\s+([^\s]+)/.exec(text);
					if (match) jsx = match[1];
				}
			}
		});
		options.jsx = jsx || options.jsx;
	} catch (err) {
		err.snippet = getSnippet(source, err.loc);
		err.toString = () => `${err.name}: ${err.message}\n${err.snippet}`;
		throw err;
	}

	const transforms = target(options.target || {});
	Object.keys(options.transforms || {}).forEach(name => {
		if (name === 'modules') {
			if (!('moduleImport' in options.transforms))
				transforms.moduleImport = options.transforms.modules;
			if (!('moduleExport' in options.transforms))
				transforms.moduleExport = options.transforms.modules;
			return;
		}

		if (!(name in transforms)) throw new Error(`Unknown transform '${name}'`);
		transforms[name] = options.transforms[name];
	});
	if (options.objectAssign === true) options.objectAssign = 'Object.assign';
	return new Program(source, ast, transforms, options).export(options);
}

export { version as VERSION } from '../package.json';
