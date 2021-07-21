'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

function _interopDefault (ex) { return (ex && (typeof ex === 'object') && 'default' in ex) ? ex['default'] : ex; }

const tslib = require('tslib');
const utils = require('@graphql-tools/utils/es5');
const process = require('process');
const graphql = require('graphql');
const isGlob = _interopDefault(require('is-glob'));
const pLimit = _interopDefault(require('p-limit'));
const importFrom = _interopDefault(require('import-from'));
const unixify = _interopDefault(require('unixify'));
const globby = require('globby');
const globby__default = _interopDefault(globby);
const merge = require('@graphql-tools/merge/es5');

function normalizePointers(unnormalizedPointerOrPointers) {
    return utils.asArray(unnormalizedPointerOrPointers).reduce(function (normalizedPointers, unnormalizedPointer) {
        if (typeof unnormalizedPointer === 'string') {
            normalizedPointers[unnormalizedPointer] = {};
        }
        else if (typeof unnormalizedPointer === 'object') {
            Object.assign(normalizedPointers, unnormalizedPointer);
        }
        else {
            throw new Error("Invalid pointer " + unnormalizedPointer);
        }
        return normalizedPointers;
    }, {});
}

function applyDefaultOptions(options) {
    options.cache = options.cache || {};
    options.cwd = options.cwd || process.cwd();
    options.sort = 'sort' in options ? options.sort : true;
}

function loadFile(pointer, options) {
    var e_1, _a;
    return tslib.__awaiter(this, void 0, void 0, function () {
        var cached, _b, _c, loader, canLoad, error_1, e_1_1;
        return tslib.__generator(this, function (_d) {
            switch (_d.label) {
                case 0:
                    cached = useCache({ pointer: pointer, options: options });
                    if (cached) {
                        return [2 /*return*/, cached];
                    }
                    _d.label = 1;
                case 1:
                    _d.trys.push([1, 11, 12, 17]);
                    _b = tslib.__asyncValues(options.loaders);
                    _d.label = 2;
                case 2: return [4 /*yield*/, _b.next()];
                case 3:
                    if (!(_c = _d.sent(), !_c.done)) return [3 /*break*/, 10];
                    loader = _c.value;
                    _d.label = 4;
                case 4:
                    _d.trys.push([4, 8, , 9]);
                    return [4 /*yield*/, loader.canLoad(pointer, options)];
                case 5:
                    canLoad = _d.sent();
                    if (!canLoad) return [3 /*break*/, 7];
                    return [4 /*yield*/, loader.load(pointer, options)];
                case 6: return [2 /*return*/, _d.sent()];
                case 7: return [3 /*break*/, 9];
                case 8:
                    error_1 = _d.sent();
                    utils.debugLog("Failed to find any GraphQL type definitions in: " + pointer + " - " + error_1.message);
                    throw error_1;
                case 9: return [3 /*break*/, 2];
                case 10: return [3 /*break*/, 17];
                case 11:
                    e_1_1 = _d.sent();
                    e_1 = { error: e_1_1 };
                    return [3 /*break*/, 17];
                case 12:
                    _d.trys.push([12, , 15, 16]);
                    if (!(_c && !_c.done && (_a = _b.return))) return [3 /*break*/, 14];
                    return [4 /*yield*/, _a.call(_b)];
                case 13:
                    _d.sent();
                    _d.label = 14;
                case 14: return [3 /*break*/, 16];
                case 15:
                    if (e_1) throw e_1.error;
                    return [7 /*endfinally*/];
                case 16: return [7 /*endfinally*/];
                case 17: return [2 /*return*/, undefined];
            }
        });
    });
}
function loadFileSync(pointer, options) {
    var e_2, _a;
    var cached = useCache({ pointer: pointer, options: options });
    if (cached) {
        return cached;
    }
    try {
        for (var _b = tslib.__values(options.loaders), _c = _b.next(); !_c.done; _c = _b.next()) {
            var loader = _c.value;
            try {
                var canLoad = loader.canLoadSync && loader.loadSync && loader.canLoadSync(pointer, options);
                if (canLoad) {
                    return loader.loadSync(pointer, options);
                }
            }
            catch (error) {
                utils.debugLog("Failed to find any GraphQL type definitions in: " + pointer + " - " + error.message);
                throw error;
            }
        }
    }
    catch (e_2_1) { e_2 = { error: e_2_1 }; }
    finally {
        try {
            if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
        }
        finally { if (e_2) throw e_2.error; }
    }
    return undefined;
}
function useCache(_a) {
    var pointer = _a.pointer, options = _a.options;
    if (options['cache']) {
        return options['cache'][pointer];
    }
}

/**
 * Converts a string to 32bit integer
 */
function stringToHash(str) {
    var hash = 0;
    if (str.length === 0) {
        return hash;
    }
    var char;
    for (var i = 0; i < str.length; i++) {
        char = str.charCodeAt(i);
        // tslint:disable-next-line: no-bitwise
        hash = (hash << 5) - hash + char;
        // tslint:disable-next-line: no-bitwise
        hash = hash & hash;
    }
    return hash;
}
function useStack() {
    var fns = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        fns[_i] = arguments[_i];
    }
    return function (input) {
        function createNext(i) {
            if (i >= fns.length) {
                return function () { };
            }
            return function next() {
                fns[i](input, createNext(i + 1));
            };
        }
        fns[0](input, createNext(1));
    };
}
function useLimit(concurrency) {
    return pLimit(concurrency);
}

function getCustomLoaderByPath(path, cwd) {
    try {
        var requiredModule = importFrom(cwd, path);
        if (requiredModule) {
            if (requiredModule.default && typeof requiredModule.default === 'function') {
                return requiredModule.default;
            }
            if (typeof requiredModule === 'function') {
                return requiredModule;
            }
        }
    }
    catch (e) { }
    return null;
}
function useCustomLoader(loaderPointer, cwd) {
    return tslib.__awaiter(this, void 0, void 0, function () {
        var loader;
        return tslib.__generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    if (!(typeof loaderPointer === 'string')) return [3 /*break*/, 2];
                    return [4 /*yield*/, getCustomLoaderByPath(loaderPointer, cwd)];
                case 1:
                    loader = _a.sent();
                    return [3 /*break*/, 3];
                case 2:
                    if (typeof loaderPointer === 'function') {
                        loader = loaderPointer;
                    }
                    _a.label = 3;
                case 3:
                    if (typeof loader !== 'function') {
                        throw new Error("Failed to load custom loader: " + loaderPointer);
                    }
                    return [2 /*return*/, loader];
            }
        });
    });
}
function useCustomLoaderSync(loaderPointer, cwd) {
    var loader;
    if (typeof loaderPointer === 'string') {
        loader = getCustomLoaderByPath(loaderPointer, cwd);
    }
    else if (typeof loaderPointer === 'function') {
        loader = loaderPointer;
    }
    if (typeof loader !== 'function') {
        throw new Error("Failed to load custom loader: " + loaderPointer);
    }
    return loader;
}

function useQueue(options) {
    var _this = this;
    var queue = [];
    var limit = (options === null || options === void 0 ? void 0 : options.concurrency) ? pLimit(options.concurrency) : function (fn) { return tslib.__awaiter(_this, void 0, void 0, function () { return tslib.__generator(this, function (_a) {
        return [2 /*return*/, fn()];
    }); }); };
    return {
        add: function (fn) {
            queue.push(function () { return limit(fn); });
        },
        runAll: function () {
            return Promise.all(queue.map(function (fn) { return fn(); }));
        },
    };
}
function useSyncQueue() {
    var queue = [];
    return {
        add: function (fn) {
            queue.push(fn);
        },
        runAll: function () {
            queue.forEach(function (fn) { return fn(); });
        },
    };
}

var CONCURRENCY_LIMIT = 50;
function collectSources(_a) {
    var _b;
    var pointerOptionMap = _a.pointerOptionMap, options = _a.options;
    return tslib.__awaiter(this, void 0, void 0, function () {
        var sources, globs, globOptions, queue, _c, addSource, addGlob, collect, pointer, pointerOptions, paths;
        return tslib.__generator(this, function (_d) {
            switch (_d.label) {
                case 0:
                    sources = [];
                    globs = [];
                    globOptions = {};
                    queue = useQueue({ concurrency: CONCURRENCY_LIMIT });
                    _c = createHelpers({
                        sources: sources,
                        globs: globs,
                        options: options,
                        globOptions: globOptions,
                        stack: [collectDocumentString, collectGlob, collectCustomLoader, collectFallback],
                    }), addSource = _c.addSource, addGlob = _c.addGlob, collect = _c.collect;
                    for (pointer in pointerOptionMap) {
                        pointerOptions = tslib.__assign(tslib.__assign({}, ((_b = pointerOptionMap[pointer]) !== null && _b !== void 0 ? _b : {})), { unixify: unixify });
                        collect({
                            pointer: pointer,
                            pointerOptions: pointerOptions,
                            pointerOptionMap: pointerOptionMap,
                            options: options,
                            addSource: addSource,
                            addGlob: addGlob,
                            queue: queue.add,
                        });
                    }
                    if (!globs.length) return [3 /*break*/, 2];
                    includeIgnored({
                        options: options,
                        globs: globs,
                    });
                    return [4 /*yield*/, globby__default(globs, createGlobbyOptions(options))];
                case 1:
                    paths = _d.sent();
                    collectSourcesFromGlobals({
                        filepaths: paths,
                        options: options,
                        globOptions: globOptions,
                        pointerOptionMap: pointerOptionMap,
                        addSource: addSource,
                        queue: queue.add,
                    });
                    _d.label = 2;
                case 2: return [4 /*yield*/, queue.runAll()];
                case 3:
                    _d.sent();
                    return [2 /*return*/, sources];
            }
        });
    });
}
function collectSourcesSync(_a) {
    var _b;
    var pointerOptionMap = _a.pointerOptionMap, options = _a.options;
    var sources = [];
    var globs = [];
    var globOptions = {};
    var queue = useSyncQueue();
    var _c = createHelpers({
        sources: sources,
        globs: globs,
        options: options,
        globOptions: globOptions,
        stack: [collectDocumentString, collectGlob, collectCustomLoaderSync, collectFallbackSync],
    }), addSource = _c.addSource, addGlob = _c.addGlob, collect = _c.collect;
    for (var pointer in pointerOptionMap) {
        var pointerOptions = tslib.__assign(tslib.__assign({}, ((_b = pointerOptionMap[pointer]) !== null && _b !== void 0 ? _b : {})), { unixify: unixify });
        collect({
            pointer: pointer,
            pointerOptions: pointerOptions,
            pointerOptionMap: pointerOptionMap,
            options: options,
            addSource: addSource,
            addGlob: addGlob,
            queue: queue.add,
        });
    }
    if (globs.length) {
        includeIgnored({
            options: options,
            globs: globs,
        });
        var paths = globby.sync(globs, createGlobbyOptions(options));
        collectSourcesFromGlobalsSync({
            filepaths: paths,
            options: options,
            globOptions: globOptions,
            pointerOptionMap: pointerOptionMap,
            addSource: addSource,
            queue: queue.add,
        });
    }
    queue.runAll();
    return sources;
}
//
function createHelpers(_a) {
    var sources = _a.sources, globs = _a.globs, options = _a.options, globOptions = _a.globOptions, stack = _a.stack;
    var addSource = function (_a) {
        var pointer = _a.pointer, source = _a.source, noCache = _a.noCache;
        sources.push(source);
        if (!noCache) {
            options.cache[pointer] = source;
        }
    };
    var collect = useStack.apply(void 0, tslib.__spread(stack));
    var addGlob = function (_a) {
        var pointerOptions = _a.pointerOptions, pointer = _a.pointer;
        globs.push(pointer);
        Object.assign(globOptions, pointerOptions);
    };
    return {
        addSource: addSource,
        collect: collect,
        addGlob: addGlob,
    };
}
function includeIgnored(_a) {
    var options = _a.options, globs = _a.globs;
    if (options.ignore) {
        var ignoreList = utils.asArray(options.ignore)
            .map(function (g) { return "!(" + g + ")"; })
            .map(unixify);
        if (ignoreList.length > 0) {
            globs.push.apply(globs, tslib.__spread(ignoreList));
        }
    }
}
function createGlobbyOptions(options) {
    return tslib.__assign(tslib.__assign({ absolute: true }, options), { ignore: [] });
}
function collectSourcesFromGlobals(_a) {
    var filepaths = _a.filepaths, options = _a.options, globOptions = _a.globOptions, pointerOptionMap = _a.pointerOptionMap, addSource = _a.addSource, queue = _a.queue;
    var collectFromGlobs = useStack(collectCustomLoader, collectFallback);
    for (var i = 0; i < filepaths.length; i++) {
        var pointer = filepaths[i];
        collectFromGlobs({
            pointer: pointer,
            pointerOptions: globOptions,
            pointerOptionMap: pointerOptionMap,
            options: options,
            addSource: addSource,
            addGlob: function () {
                throw new Error("I don't accept any new globs!");
            },
            queue: queue,
        });
    }
}
function collectSourcesFromGlobalsSync(_a) {
    var filepaths = _a.filepaths, options = _a.options, globOptions = _a.globOptions, pointerOptionMap = _a.pointerOptionMap, addSource = _a.addSource, queue = _a.queue;
    var collectFromGlobs = useStack(collectCustomLoaderSync, collectFallbackSync);
    for (var i = 0; i < filepaths.length; i++) {
        var pointer = filepaths[i];
        collectFromGlobs({
            pointer: pointer,
            pointerOptions: globOptions,
            pointerOptionMap: pointerOptionMap,
            options: options,
            addSource: addSource,
            addGlob: function () {
                throw new Error("I don't accept any new globs!");
            },
            queue: queue,
        });
    }
}
function addResultOfCustomLoader(_a) {
    var pointer = _a.pointer, result = _a.result, addSource = _a.addSource;
    if (graphql.isSchema(result)) {
        addSource({
            source: {
                location: pointer,
                schema: result,
                document: graphql.parse(utils.printSchemaWithDirectives(result)),
            },
            pointer: pointer,
            noCache: true,
        });
    }
    else if (result.kind && result.kind === graphql.Kind.DOCUMENT) {
        addSource({
            source: {
                document: result,
                location: pointer,
            },
            pointer: pointer,
        });
    }
    else if (result.document) {
        addSource({
            source: tslib.__assign({ location: pointer }, result),
            pointer: pointer,
        });
    }
}
function collectDocumentString(_a, next) {
    var pointer = _a.pointer, pointerOptions = _a.pointerOptions, options = _a.options, addSource = _a.addSource, queue = _a.queue;
    if (utils.isDocumentString(pointer)) {
        return queue(function () {
            var source = utils.parseGraphQLSDL(stringToHash(pointer) + ".graphql", pointer, tslib.__assign(tslib.__assign({}, options), pointerOptions));
            addSource({
                source: source,
                pointer: pointer,
            });
        });
    }
    next();
}
function collectGlob(_a, next) {
    var pointer = _a.pointer, pointerOptions = _a.pointerOptions, addGlob = _a.addGlob;
    if (isGlob(pointerOptions.unixify(pointer))) {
        return addGlob({
            pointer: pointerOptions.unixify(pointer),
            pointerOptions: pointerOptions,
        });
    }
    next();
}
function collectCustomLoader(_a, next) {
    var _this = this;
    var pointer = _a.pointer, pointerOptions = _a.pointerOptions, queue = _a.queue, addSource = _a.addSource, options = _a.options, pointerOptionMap = _a.pointerOptionMap;
    if (pointerOptions.loader) {
        return queue(function () { return tslib.__awaiter(_this, void 0, void 0, function () {
            var loader, result;
            return tslib.__generator(this, function (_a) {
                switch (_a.label) {
                    case 0: return [4 /*yield*/, useCustomLoader(pointerOptions.loader, options.cwd)];
                    case 1:
                        loader = _a.sent();
                        return [4 /*yield*/, loader(pointer, tslib.__assign(tslib.__assign({}, options), pointerOptions), pointerOptionMap)];
                    case 2:
                        result = _a.sent();
                        if (!result) {
                            return [2 /*return*/];
                        }
                        addResultOfCustomLoader({ pointer: pointer, result: result, addSource: addSource });
                        return [2 /*return*/];
                }
            });
        }); });
    }
    next();
}
function collectCustomLoaderSync(_a, next) {
    var pointer = _a.pointer, pointerOptions = _a.pointerOptions, queue = _a.queue, addSource = _a.addSource, options = _a.options, pointerOptionMap = _a.pointerOptionMap;
    if (pointerOptions.loader) {
        return queue(function () {
            var loader = useCustomLoaderSync(pointerOptions.loader, options.cwd);
            var result = loader(pointer, tslib.__assign(tslib.__assign({}, options), pointerOptions), pointerOptionMap);
            if (result) {
                addResultOfCustomLoader({ pointer: pointer, result: result, addSource: addSource });
            }
        });
    }
    next();
}
function collectFallback(_a) {
    var _this = this;
    var queue = _a.queue, pointer = _a.pointer, options = _a.options, pointerOptions = _a.pointerOptions, addSource = _a.addSource;
    return queue(function () { return tslib.__awaiter(_this, void 0, void 0, function () {
        var source;
        return tslib.__generator(this, function (_a) {
            switch (_a.label) {
                case 0: return [4 /*yield*/, loadFile(pointer, tslib.__assign(tslib.__assign({}, options), pointerOptions))];
                case 1:
                    source = _a.sent();
                    if (source) {
                        addSource({ source: source, pointer: pointer });
                    }
                    return [2 /*return*/];
            }
        });
    }); });
}
function collectFallbackSync(_a) {
    var queue = _a.queue, pointer = _a.pointer, options = _a.options, pointerOptions = _a.pointerOptions, addSource = _a.addSource;
    return queue(function () {
        var source = loadFileSync(pointer, tslib.__assign(tslib.__assign({}, options), pointerOptions));
        if (source) {
            addSource({ source: source, pointer: pointer });
        }
    });
}

/**
 * @internal
 */
var filterKind = function (content, filterKinds) {
    var e_1, _a;
    if (content && content.definitions && content.definitions.length && filterKinds && filterKinds.length > 0) {
        var invalidDefinitions = [];
        var validDefinitions = [];
        try {
            for (var _b = tslib.__values(content.definitions), _c = _b.next(); !_c.done; _c = _b.next()) {
                var definitionNode = _c.value;
                if (filterKinds.includes(definitionNode.kind)) {
                    invalidDefinitions.push(definitionNode);
                }
                else {
                    validDefinitions.push(definitionNode);
                }
            }
        }
        catch (e_1_1) { e_1 = { error: e_1_1 }; }
        finally {
            try {
                if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
            }
            finally { if (e_1) throw e_1.error; }
        }
        if (invalidDefinitions.length > 0) {
            invalidDefinitions.forEach(function (d) {
                utils.debugLog("Filtered document of kind " + d.kind + " due to filter policy (" + filterKinds.join(', ') + ")");
            });
        }
        return {
            kind: graphql.Kind.DOCUMENT,
            definitions: validDefinitions,
        };
    }
    return content;
};

function parseSource(_a) {
    var partialSource = _a.partialSource, options = _a.options, globOptions = _a.globOptions, pointerOptionMap = _a.pointerOptionMap, addValidSource = _a.addValidSource;
    if (partialSource) {
        var input = prepareInput({
            source: partialSource,
            options: options,
            globOptions: globOptions,
            pointerOptionMap: pointerOptionMap,
        });
        parseSchema(input);
        parseRawSDL(input);
        if (input.source.document) {
            useKindsFilter(input);
            useComments(input);
            collectValidSources(input, addValidSource);
        }
    }
}
//
function prepareInput(_a) {
    var source = _a.source, options = _a.options, globOptions = _a.globOptions, pointerOptionMap = _a.pointerOptionMap;
    var specificOptions = tslib.__assign(tslib.__assign({}, options), (source.location in pointerOptionMap ? globOptions : pointerOptionMap[source.location]));
    return { source: tslib.__assign({}, source), options: specificOptions };
}
function parseSchema(input) {
    if (input.source.schema) {
        input.source.schema = utils.fixSchemaAst(input.source.schema, input.options);
        input.source.rawSDL = utils.printSchemaWithDirectives(input.source.schema, input.options);
    }
}
function parseRawSDL(input) {
    if (input.source.rawSDL) {
        input.source.document = utils.parseGraphQLSDL(input.source.location, input.source.rawSDL, input.options).document;
    }
}
function useKindsFilter(input) {
    if (input.options.filterKinds) {
        input.source.document = filterKind(input.source.document, input.options.filterKinds);
    }
}
function useComments(input) {
    if (!input.source.rawSDL) {
        input.source.rawSDL = merge.printWithComments(input.source.document);
        merge.resetComments();
    }
}
function collectValidSources(input, addValidSource) {
    if (input.source.document.definitions && input.source.document.definitions.length > 0) {
        addValidSource(input.source);
    }
}

var CONCURRENCY_LIMIT$1 = 100;
/**
 * Asynchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
function loadTypedefs(pointerOrPointers, options) {
    return tslib.__awaiter(this, void 0, void 0, function () {
        var pointerOptionMap, globOptions, sources, validSources, limit;
        return tslib.__generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    pointerOptionMap = normalizePointers(pointerOrPointers);
                    globOptions = {};
                    applyDefaultOptions(options);
                    return [4 /*yield*/, collectSources({
                            pointerOptionMap: pointerOptionMap,
                            options: options,
                        })];
                case 1:
                    sources = _a.sent();
                    validSources = [];
                    limit = useLimit(CONCURRENCY_LIMIT$1);
                    return [4 /*yield*/, Promise.all(sources.map(function (partialSource) {
                            return limit(function () {
                                return parseSource({
                                    partialSource: partialSource,
                                    options: options,
                                    globOptions: globOptions,
                                    pointerOptionMap: pointerOptionMap,
                                    addValidSource: function (source) {
                                        validSources.push(source);
                                    },
                                });
                            });
                        }))];
                case 2:
                    _a.sent();
                    return [2 /*return*/, prepareResult({ options: options, pointerOptionMap: pointerOptionMap, validSources: validSources })];
            }
        });
    });
}
/**
 * Synchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
function loadTypedefsSync(pointerOrPointers, options) {
    var pointerOptionMap = normalizePointers(pointerOrPointers);
    var globOptions = {};
    applyDefaultOptions(options);
    var sources = collectSourcesSync({
        pointerOptionMap: pointerOptionMap,
        options: options,
    });
    var validSources = [];
    sources.forEach(function (partialSource) {
        parseSource({
            partialSource: partialSource,
            options: options,
            globOptions: globOptions,
            pointerOptionMap: pointerOptionMap,
            addValidSource: function (source) {
                validSources.push(source);
            },
        });
    });
    return prepareResult({ options: options, pointerOptionMap: pointerOptionMap, validSources: validSources });
}
//
function prepareResult(_a) {
    var options = _a.options, pointerOptionMap = _a.pointerOptionMap, validSources = _a.validSources;
    var pointerList = Object.keys(pointerOptionMap);
    if (pointerList.length > 0 && validSources.length === 0) {
        throw new Error("\n      Unable to find any GraphQL type definitions for the following pointers:\n        " + pointerList.map(function (p) { return "\n          - " + p + "\n          "; }));
    }
    return options.sort
        ? validSources.sort(function (left, right) { return utils.compareStrings(left.location, right.location); })
        : validSources;
}

/**
 * Kinds of AST nodes that are included in executable documents
 */
var OPERATION_KINDS = [graphql.Kind.OPERATION_DEFINITION, graphql.Kind.FRAGMENT_DEFINITION];
/**
 * Kinds of AST nodes that are included in type system definition documents
 */
var NON_OPERATION_KINDS = Object.keys(graphql.Kind)
    .reduce(function (prev, v) { return tslib.__spread(prev, [graphql.Kind[v]]); }, [])
    .filter(function (v) { return !OPERATION_KINDS.includes(v); });
/**
 * Asynchronously loads executable documents (i.e. operations and fragments) from
 * the provided pointers. The pointers may be individual files or a glob pattern.
 * The files themselves may be `.graphql` files or `.js` and `.ts` (in which
 * case they will be parsed using graphql-tag-pluck).
 * @param pointerOrPointers Pointers to the files to load the documents from
 * @param options Additional options
 */
function loadDocuments(pointerOrPointers, options) {
    return loadTypedefs(pointerOrPointers, tslib.__assign({ noRequire: true, filterKinds: NON_OPERATION_KINDS }, options));
}
/**
 * Synchronously loads executable documents (i.e. operations and fragments) from
 * the provided pointers. The pointers may be individual files or a glob pattern.
 * The files themselves may be `.graphql` files or `.js` and `.ts` (in which
 * case they will be parsed using graphql-tag-pluck).
 * @param pointerOrPointers Pointers to the files to load the documents from
 * @param options Additional options
 */
function loadDocumentsSync(pointerOrPointers, options) {
    return loadTypedefsSync(pointerOrPointers, tslib.__assign({ noRequire: true, filterKinds: NON_OPERATION_KINDS }, options));
}

/**
 * Asynchronously loads a schema from the provided pointers.
 * @param schemaPointers Pointers to the sources to load the schema from
 * @param options Additional options
 */
function loadSchema(schemaPointers, options) {
    return tslib.__awaiter(this, void 0, void 0, function () {
        var sources, _a, schemas, typeDefs, mergeSchemasOptions, schema;
        return tslib.__generator(this, function (_b) {
            switch (_b.label) {
                case 0: return [4 /*yield*/, loadTypedefs(schemaPointers, tslib.__assign({ filterKinds: OPERATION_KINDS }, options))];
                case 1:
                    sources = _b.sent();
                    _a = collectSchemasAndTypeDefs(sources), schemas = _a.schemas, typeDefs = _a.typeDefs;
                    mergeSchemasOptions = tslib.__assign({ schemas: schemas,
                        typeDefs: typeDefs }, options);
                    return [4 /*yield*/, merge.mergeSchemasAsync(mergeSchemasOptions)];
                case 2:
                    schema = _b.sent();
                    if (options === null || options === void 0 ? void 0 : options.includeSources) {
                        includeSources(schema, sources);
                    }
                    return [2 /*return*/, schema];
            }
        });
    });
}
/**
 * Synchronously loads a schema from the provided pointers.
 * @param schemaPointers Pointers to the sources to load the schema from
 * @param options Additional options
 */
function loadSchemaSync(schemaPointers, options) {
    var sources = loadTypedefsSync(schemaPointers, tslib.__assign({ filterKinds: OPERATION_KINDS }, options));
    var _a = collectSchemasAndTypeDefs(sources), schemas = _a.schemas, typeDefs = _a.typeDefs;
    var mergeSchemasOptions = tslib.__assign({ schemas: schemas,
        typeDefs: typeDefs }, options);
    var schema = merge.mergeSchemas(mergeSchemasOptions);
    if (options === null || options === void 0 ? void 0 : options.includeSources) {
        includeSources(schema, sources);
    }
    return schema;
}
function includeSources(schema, sources) {
    schema.extensions = tslib.__assign(tslib.__assign({}, schema.extensions), { sources: sources
            .filter(function (source) { return source.rawSDL || source.document; })
            .map(function (source) { return new graphql.Source(source.rawSDL || graphql.print(source.document), source.location); }) });
}
function collectSchemasAndTypeDefs(sources) {
    var schemas = [];
    var typeDefs = [];
    sources.forEach(function (source) {
        if (source.schema) {
            schemas.push(source.schema);
        }
        else {
            typeDefs.push(source.document);
        }
    });
    return {
        schemas: schemas,
        typeDefs: typeDefs,
    };
}

exports.NON_OPERATION_KINDS = NON_OPERATION_KINDS;
exports.OPERATION_KINDS = OPERATION_KINDS;
exports.filterKind = filterKind;
exports.loadDocuments = loadDocuments;
exports.loadDocumentsSync = loadDocumentsSync;
exports.loadSchema = loadSchema;
exports.loadSchemaSync = loadSchemaSync;
exports.loadTypedefs = loadTypedefs;
exports.loadTypedefsSync = loadTypedefsSync;
//# sourceMappingURL=index.cjs.js.map
