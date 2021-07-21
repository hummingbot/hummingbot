/*
  @license
	Rollup.js v1.23.1
	Sat, 05 Oct 2019 06:08:56 GMT - commit 53266e6b971fff985b273800d808b17084d5c41b


	https://github.com/rollup/rollup

	Released under the MIT License.
*/
'use strict';

var path = require('path');
var module$1 = require('module');

var version = "1.23.1";

function createCommonjsModule(fn, module) {
	return module = { exports: {} }, fn(module, module.exports), module.exports;
}

const absolutePath = /^(?:\/|(?:[A-Za-z]:)?[\\|/])/;
const relativePath = /^\.?\.\//;
function isAbsolute(path) {
    return absolutePath.test(path);
}
function isRelative(path) {
    return relativePath.test(path);
}
function normalize(path) {
    if (path.indexOf('\\') == -1)
        return path;
    return path.replace(/\\/g, '/');
}

function sanitizeFileName(name) {
    return name.replace(/[\0?*]/g, '_');
}

function getAliasName(id) {
    const base = path.basename(id);
    return base.substr(0, base.length - path.extname(id).length);
}
function relativeId(id) {
    if (typeof process === 'undefined' || !isAbsolute(id))
        return id;
    return path.relative(process.cwd(), id);
}
function isPlainPathFragment(name) {
    // not starting with "/", "./", "../"
    return (name[0] !== '/' &&
        !(name[0] === '.' && (name[1] === '/' || name[1] === '.')) &&
        sanitizeFileName(name) === name);
}

const createGetOption = (config, command) => (name, defaultValue) => command[name] !== undefined
    ? command[name]
    : config[name] !== undefined
        ? config[name]
        : defaultValue;
const normalizeObjectOptionValue = (optionValue) => {
    if (!optionValue) {
        return optionValue;
    }
    if (typeof optionValue !== 'object') {
        return {};
    }
    return optionValue;
};
const getObjectOption = (config, command, name) => {
    const commandOption = normalizeObjectOptionValue(command[name]);
    const configOption = normalizeObjectOptionValue(config[name]);
    if (commandOption !== undefined) {
        return commandOption && configOption ? Object.assign(Object.assign({}, configOption), commandOption) : commandOption;
    }
    return configOption;
};
const defaultOnWarn = warning => {
    if (typeof warning === 'string') {
        console.warn(warning);
    }
    else {
        console.warn(warning.message);
    }
};
const getOnWarn = (config, defaultOnWarnHandler = defaultOnWarn) => config.onwarn
    ? warning => config.onwarn(warning, defaultOnWarnHandler)
    : defaultOnWarnHandler;
const getExternal = (config, command) => {
    const configExternal = config.external;
    return typeof configExternal === 'function'
        ? (id, ...rest) => configExternal(id, ...rest) || command.external.indexOf(id) !== -1
        : (typeof config.external === 'string'
            ? [configExternal]
            : Array.isArray(configExternal)
                ? configExternal
                : []).concat(command.external);
};
const commandAliases = {
    c: 'config',
    d: 'dir',
    e: 'external',
    f: 'format',
    g: 'globals',
    h: 'help',
    i: 'input',
    m: 'sourcemap',
    n: 'name',
    o: 'file',
    v: 'version',
    w: 'watch'
};
function mergeOptions({ config = {}, command: rawCommandOptions = {}, defaultOnWarnHandler }) {
    const command = getCommandOptions(rawCommandOptions);
    const inputOptions = getInputOptions(config, command, defaultOnWarnHandler);
    if (command.output) {
        Object.assign(command, command.output);
    }
    const output = config.output;
    const normalizedOutputOptions = Array.isArray(output) ? output : output ? [output] : [];
    if (normalizedOutputOptions.length === 0)
        normalizedOutputOptions.push({});
    const outputOptions = normalizedOutputOptions.map(singleOutputOptions => getOutputOptions(singleOutputOptions, command));
    const unknownOptionErrors = [];
    const validInputOptions = Object.keys(inputOptions);
    addUnknownOptionErrors(unknownOptionErrors, Object.keys(config), validInputOptions, 'input option', /^output$/);
    const validOutputOptions = Object.keys(outputOptions[0]);
    addUnknownOptionErrors(unknownOptionErrors, outputOptions.reduce((allKeys, options) => allKeys.concat(Object.keys(options)), []), validOutputOptions, 'output option');
    const validCliOutputOptions = validOutputOptions.filter(option => option !== 'sourcemapPathTransform');
    addUnknownOptionErrors(unknownOptionErrors, Object.keys(command), validInputOptions.concat(validCliOutputOptions, Object.keys(commandAliases), 'config', 'environment', 'silent'), 'CLI flag', /^_|output|(config.*)$/);
    return {
        inputOptions,
        optionError: unknownOptionErrors.length > 0 ? unknownOptionErrors.join('\n') : null,
        outputOptions
    };
}
function addUnknownOptionErrors(errors, options, validOptions, optionType, ignoredKeys = /$./) {
    const unknownOptions = options.filter(key => validOptions.indexOf(key) === -1 && !ignoredKeys.test(key));
    if (unknownOptions.length > 0)
        errors.push(`Unknown ${optionType}: ${unknownOptions.join(', ')}. Allowed options: ${validOptions.sort().join(', ')}`);
}
function getCommandOptions(rawCommandOptions) {
    const external = rawCommandOptions.external && typeof rawCommandOptions.external === 'string'
        ? rawCommandOptions.external.split(',')
        : [];
    return Object.assign(Object.assign({}, rawCommandOptions), { external, globals: typeof rawCommandOptions.globals === 'string'
            ? rawCommandOptions.globals.split(',').reduce((globals, globalDefinition) => {
                const [id, variableName] = globalDefinition.split(':');
                globals[id] = variableName;
                if (external.indexOf(id) === -1) {
                    external.push(id);
                }
                return globals;
            }, Object.create(null))
            : undefined });
}
function getInputOptions(config, command = { external: [], globals: undefined }, defaultOnWarnHandler) {
    const getOption = createGetOption(config, command);
    const inputOptions = {
        acorn: config.acorn,
        acornInjectPlugins: config.acornInjectPlugins,
        cache: getOption('cache'),
        chunkGroupingSize: getOption('chunkGroupingSize', 5000),
        context: getOption('context'),
        experimentalCacheExpiry: getOption('experimentalCacheExpiry', 10),
        experimentalOptimizeChunks: getOption('experimentalOptimizeChunks'),
        experimentalTopLevelAwait: getOption('experimentalTopLevelAwait'),
        external: getExternal(config, command),
        inlineDynamicImports: getOption('inlineDynamicImports', false),
        input: getOption('input', []),
        manualChunks: getOption('manualChunks'),
        moduleContext: config.moduleContext,
        onwarn: getOnWarn(config, defaultOnWarnHandler),
        perf: getOption('perf', false),
        plugins: config.plugins,
        preserveModules: getOption('preserveModules'),
        preserveSymlinks: getOption('preserveSymlinks'),
        shimMissingExports: getOption('shimMissingExports'),
        strictDeprecations: getOption('strictDeprecations', false),
        treeshake: getObjectOption(config, command, 'treeshake'),
        watch: config.watch
    };
    // support rollup({ cache: prevBuildObject })
    if (inputOptions.cache && inputOptions.cache.cache)
        inputOptions.cache = inputOptions.cache.cache;
    return inputOptions;
}
function getOutputOptions(config, command = {}) {
    const getOption = createGetOption(config, command);
    let format = getOption('format');
    // Handle format aliases
    switch (format) {
        case 'esm':
        case 'module':
            format = 'es';
            break;
        case 'commonjs':
            format = 'cjs';
    }
    return {
        amd: Object.assign(Object.assign({}, config.amd), command.amd),
        assetFileNames: getOption('assetFileNames'),
        banner: getOption('banner'),
        chunkFileNames: getOption('chunkFileNames'),
        compact: getOption('compact', false),
        dir: getOption('dir'),
        dynamicImportFunction: getOption('dynamicImportFunction'),
        entryFileNames: getOption('entryFileNames'),
        esModule: getOption('esModule', true),
        exports: getOption('exports'),
        extend: getOption('extend'),
        externalLiveBindings: getOption('externalLiveBindings', true),
        file: getOption('file'),
        footer: getOption('footer'),
        format: format === 'esm' ? 'es' : format,
        freeze: getOption('freeze', true),
        globals: getOption('globals'),
        indent: getOption('indent', true),
        interop: getOption('interop', true),
        intro: getOption('intro'),
        name: getOption('name'),
        namespaceToStringTag: getOption('namespaceToStringTag', false),
        noConflict: getOption('noConflict'),
        outro: getOption('outro'),
        paths: getOption('paths'),
        preferConst: getOption('preferConst'),
        sourcemap: getOption('sourcemap'),
        sourcemapExcludeSources: getOption('sourcemapExcludeSources'),
        sourcemapFile: getOption('sourcemapFile'),
        sourcemapPathTransform: getOption('sourcemapPathTransform'),
        strict: getOption('strict', true)
    };
}

var modules = {};
var getModule = function (dir) {
    var rootPath = dir ? path.resolve(dir) : process.cwd();
    var rootName = path.join(rootPath, '@root');
    var root = modules[rootName];
    if (!root) {
        root = new module$1(rootName);
        root.filename = rootName;
        root.paths = module$1._nodeModulePaths(rootPath);
        modules[rootName] = root;
    }
    return root;
};
var requireRelative = function (requested, relativeTo) {
    var root = getModule(relativeTo);
    return root.require(requested);
};
requireRelative.resolve = function (requested, relativeTo) {
    var root = getModule(relativeTo);
    return module$1._resolveFilename(requested, root);
};
var requireRelative_1 = requireRelative;

exports.commandAliases = commandAliases;
exports.createCommonjsModule = createCommonjsModule;
exports.getAliasName = getAliasName;
exports.isAbsolute = isAbsolute;
exports.isPlainPathFragment = isPlainPathFragment;
exports.isRelative = isRelative;
exports.mergeOptions = mergeOptions;
exports.normalize = normalize;
exports.path = path;
exports.relative = requireRelative_1;
exports.relativeId = relativeId;
exports.sanitizeFileName = sanitizeFileName;
exports.version = version;
//# sourceMappingURL=index.js.map
