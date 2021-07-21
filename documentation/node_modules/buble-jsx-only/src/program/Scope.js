import extractNames from './extractNames.js';
import reserved from '../utils/reserved.js';

export default function Scope(options) {
	options = options || {};

	this.parent = options.parent;
	this.isBlockScope = !!options.block;
	this.createDeclarationCallback = options.declare;

	let scope = this;
	while (scope.isBlockScope) scope = scope.parent;
	this.functionScope = scope;

	this.identifiers = [];
	this.declarations = Object.create(null);
	this.references = Object.create(null);
	this.blockScopedDeclarations = this.isBlockScope ? null : Object.create(null);
	this.aliases = Object.create(null);
}

Scope.prototype = {
	addDeclaration(node, kind) {
		for (const identifier of extractNames(node)) {
			const name = identifier.name;

			const declaration = { name, node: identifier, kind, instances: [] };
			this.declarations[name] = declaration;

			if (this.isBlockScope) {
				if (!this.functionScope.blockScopedDeclarations[name])
					this.functionScope.blockScopedDeclarations[name] = [];
				this.functionScope.blockScopedDeclarations[name].push(declaration);
			}
		}
	},

	addReference(identifier) {
		if (this.consolidated) {
			this.consolidateReference(identifier);
		} else {
			this.identifiers.push(identifier);
		}
	},

	consolidate() {
		for (let i = 0; i < this.identifiers.length; i += 1) {
			// we might push to the array during consolidation, so don't cache length
			const identifier = this.identifiers[i];
			this.consolidateReference(identifier);
		}

		this.consolidated = true; // TODO understand why this is necessary... seems bad
	},

	consolidateReference(identifier) {
		const declaration = this.declarations[identifier.name];
		if (declaration) {
			declaration.instances.push(identifier);
		} else {
			this.references[identifier.name] = true;
			if (this.parent) this.parent.addReference(identifier);
		}
	},

	contains(name) {
		return (
			this.declarations[name] ||
			(this.parent ? this.parent.contains(name) : false)
		);
	},

	createIdentifier(base) {
		if (typeof base === 'number') base = base.toString();

		base = base
			.replace(/\s/g, '')
			.replace(/\[([^\]]+)\]/g, '_$1')
			.replace(/[^a-zA-Z0-9_$]/g, '_')
			.replace(/_{2,}/, '_');

		let name = base;
		let counter = 1;

		while (
			this.declarations[name] ||
			this.references[name] ||
			this.aliases[name] ||
			name in reserved
		) {
			name = `${base}$${counter++}`;
		}

		this.aliases[name] = true;
		return name;
	},

	createDeclaration(base) {
		const id = this.createIdentifier(base);
		this.createDeclarationCallback(id);
		return id;
	},

	findDeclaration(name) {
		return (
			this.declarations[name] ||
			(this.parent && this.parent.findDeclaration(name))
		);
	},

	// Sometimes, block scope declarations change name during transpilation
	resolveName(name) {
		const declaration = this.findDeclaration(name);
		return declaration ? declaration.name : name;
	}
};
