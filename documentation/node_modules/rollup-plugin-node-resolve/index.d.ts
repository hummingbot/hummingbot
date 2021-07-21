import {Plugin} from 'rollup';
import {AsyncOpts} from 'resolve';

export interface Options {
	/**
	 * the fields to scan in a package.json to determine the entry point
	 * if this list contains "browser", overrides specified in "pkg.browser"
	 * will be used
	 * @default ['module', 'main']
	 */
	mainFields?: ReadonlyArray<string>;

	/**
	 * @deprecated use "mainFields" instead
	 * use "module" field for ES6 module if possible
	 * @default true
	 */
	module?: boolean;

	/**
	 * @deprecated use "mainFields" instead
	 * use "jsnext:main" if possible
	 * legacy field pointing to ES6 module in third-party libraries,
	 * deprecated in favor of "pkg.module":
	 * - see: https://github.com/rollup/rollup/wiki/pkg.module
	 * @default false
	 */
	jsnext?: boolean;

	/**
	 * @deprecated use "mainFields" instead
	 * use "main" field or index.js, even if it's not an ES6 module
	 * (needs to be converted from CommonJS to ES6)
	 * – see https://github.com/rollup/rollup-plugin-commonjs
	 * @default true
	 */
	main?: boolean;

	/**
	 * some package.json files have a "browser" field which specifies
	 * alternative files to load for people bundling for the browser. If
	 * that's you, either use this option or add "browser" to the
	 * "mainfields" option, otherwise pkg.browser will be ignored
	 * @default false
	 */
	browser?: boolean;

	/**
	 * not all files you want to resolve are .js files
	 * @default [ '.mjs', '.js', '.json', '.node' ]
	 */
	extensions?: ReadonlyArray<string>;

	/**
	 * whether to prefer built-in modules (e.g. `fs`, `path`) or
	 * local ones with the same names
	 * @default true
	 */
	preferBuiltins?: boolean;

	/**
	 * Lock the module search in this path (like a chroot). Module defined
	 * outside this path will be marked as external
	 * @default '/'
	 */
	jail?: string;

	/**
	 * Set to an array of strings and/or regexps to lock the module search
	 * to modules that match at least one entry. Modules not matching any
	 * entry will be marked as external
	 * @default null
	 */
	only?: ReadonlyArray<string | RegExp> | null;

	/**
	 * If true, inspect resolved files to check that they are
	 * ES2015 modules
	 * @default false
	 */
	modulesOnly?: boolean;

	/**
	 * Force resolving for these modules to root's node_modules that helps
	 * to prevent bundling the same package multiple times if package is
	 * imported from dependencies.
	 */
	dedupe?: string[] | ((importee: string) => boolean);

	/**
	 * Any additional options that should be passed through
	 * to node-resolve
	 */
	customResolveOptions?: AsyncOpts;
}

/**
 * Locate modules using the Node resolution algorithm, for using third party modules in node_modules
 */
export default function nodeResolve(options?: Options): Plugin;
