import MagicString from 'magic-string';
import BlockStatement from './BlockStatement.js';
import wrap from './wrap.js';

export default function Program(source, ast, transforms, options) {
	this.type = 'Root';

	// options
	this.jsx = options.jsx || 'React.createElement';
	this.jsxFragment = options.jsxFragment || 'React.Fragment';
	this.options = options;

	this.source = source;
	this.magicString = new MagicString(source);

	this.ast = ast;
	this.depth = 0;

	wrap((this.body = ast), this);
	this.body.__proto__ = BlockStatement.prototype;

	this.templateLiteralQuasis = Object.create(null);
	for (let i = 0; i < this.body.body.length; ++i) {
		if (!this.body.body[i].directive) {
			this.prependAt = this.body.body[i].start;
			break;
		}
	}
	this.objectWithoutPropertiesHelper = null;

	this.indentExclusionElements = [];
	this.body.initialise(transforms);

	this.indentExclusions = Object.create(null);
	for (const node of this.indentExclusionElements) {
		for (let i = node.start; i < node.end; i += 1) {
			this.indentExclusions[i] = true;
		}
	}

	this.body.transpile(this.magicString, transforms);
}

Program.prototype = {
	export(options = {}) {
		return {
			code: this.magicString.toString(),
			map: this.magicString.generateMap({
				file: options.file,
				source: options.source,
				includeContent: options.includeContent !== false
			})
		};
	},

	findNearest() {
		return null;
	},

	findScope() {
		return null;
	},

	getObjectWithoutPropertiesHelper(code) {
		if (!this.objectWithoutPropertiesHelper) {
			this.objectWithoutPropertiesHelper = this.body.scope.createIdentifier('objectWithoutProperties');
			code.prependLeft(this.prependAt, `function ${this.objectWithoutPropertiesHelper} (obj, exclude) { ` +
				`var target = {}; for (var k in obj) ` +
				`if (Object.prototype.hasOwnProperty.call(obj, k) && exclude.indexOf(k) === -1) ` +
				`target[k] = obj[k]; return target; }\n`
			);
		}
		return this.objectWithoutPropertiesHelper;
	}
};
