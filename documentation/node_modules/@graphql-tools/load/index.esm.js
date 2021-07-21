import { asArray, debugLog, printSchemaWithDirectives, isDocumentString, parseGraphQLSDL, fixSchemaAst, compareStrings } from '@graphql-tools/utils';
import { cwd } from 'process';
import { isSchema, parse, Kind, Source, print } from 'graphql';
import isGlob from 'is-glob';
import pLimit from 'p-limit';
import importFrom from 'import-from';
import unixify from 'unixify';
import globby, { sync } from 'globby';
import { printWithComments, resetComments, mergeSchemasAsync, mergeSchemas } from '@graphql-tools/merge';

function normalizePointers(unnormalizedPointerOrPointers) {
    return asArray(unnormalizedPointerOrPointers).reduce((normalizedPointers, unnormalizedPointer) => {
        if (typeof unnormalizedPointer === 'string') {
            normalizedPointers[unnormalizedPointer] = {};
        }
        else if (typeof unnormalizedPointer === 'object') {
            Object.assign(normalizedPointers, unnormalizedPointer);
        }
        else {
            throw new Error(`Invalid pointer ${unnormalizedPointer}`);
        }
        return normalizedPointers;
    }, {});
}

function applyDefaultOptions(options) {
    options.cache = options.cache || {};
    options.cwd = options.cwd || cwd();
    options.sort = 'sort' in options ? options.sort : true;
}

async function loadFile(pointer, options) {
    const cached = useCache({ pointer, options });
    if (cached) {
        return cached;
    }
    for await (const loader of options.loaders) {
        try {
            const canLoad = await loader.canLoad(pointer, options);
            if (canLoad) {
                return await loader.load(pointer, options);
            }
        }
        catch (error) {
            debugLog(`Failed to find any GraphQL type definitions in: ${pointer} - ${error.message}`);
            throw error;
        }
    }
    return undefined;
}
function loadFileSync(pointer, options) {
    const cached = useCache({ pointer, options });
    if (cached) {
        return cached;
    }
    for (const loader of options.loaders) {
        try {
            const canLoad = loader.canLoadSync && loader.loadSync && loader.canLoadSync(pointer, options);
            if (canLoad) {
                return loader.loadSync(pointer, options);
            }
        }
        catch (error) {
            debugLog(`Failed to find any GraphQL type definitions in: ${pointer} - ${error.message}`);
            throw error;
        }
    }
    return undefined;
}
function useCache({ pointer, options }) {
    if (options['cache']) {
        return options['cache'][pointer];
    }
}

/**
 * Converts a string to 32bit integer
 */
function stringToHash(str) {
    let hash = 0;
    if (str.length === 0) {
        return hash;
    }
    let char;
    for (let i = 0; i < str.length; i++) {
        char = str.charCodeAt(i);
        // tslint:disable-next-line: no-bitwise
        hash = (hash << 5) - hash + char;
        // tslint:disable-next-line: no-bitwise
        hash = hash & hash;
    }
    return hash;
}
function useStack(...fns) {
    return (input) => {
        function createNext(i) {
            if (i >= fns.length) {
                return () => { };
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
        const requiredModule = importFrom(cwd, path);
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
async function useCustomLoader(loaderPointer, cwd) {
    let loader;
    if (typeof loaderPointer === 'string') {
        loader = await getCustomLoaderByPath(loaderPointer, cwd);
    }
    else if (typeof loaderPointer === 'function') {
        loader = loaderPointer;
    }
    if (typeof loader !== 'function') {
        throw new Error(`Failed to load custom loader: ${loaderPointer}`);
    }
    return loader;
}
function useCustomLoaderSync(loaderPointer, cwd) {
    let loader;
    if (typeof loaderPointer === 'string') {
        loader = getCustomLoaderByPath(loaderPointer, cwd);
    }
    else if (typeof loaderPointer === 'function') {
        loader = loaderPointer;
    }
    if (typeof loader !== 'function') {
        throw new Error(`Failed to load custom loader: ${loaderPointer}`);
    }
    return loader;
}

function useQueue(options) {
    const queue = [];
    const limit = (options === null || options === void 0 ? void 0 : options.concurrency) ? pLimit(options.concurrency) : async (fn) => fn();
    return {
        add(fn) {
            queue.push(() => limit(fn));
        },
        runAll() {
            return Promise.all(queue.map(fn => fn()));
        },
    };
}
function useSyncQueue() {
    const queue = [];
    return {
        add(fn) {
            queue.push(fn);
        },
        runAll() {
            queue.forEach(fn => fn());
        },
    };
}

const CONCURRENCY_LIMIT = 50;
async function collectSources({ pointerOptionMap, options, }) {
    var _a;
    const sources = [];
    const globs = [];
    const globOptions = {};
    const queue = useQueue({ concurrency: CONCURRENCY_LIMIT });
    const { addSource, addGlob, collect } = createHelpers({
        sources,
        globs,
        options,
        globOptions,
        stack: [collectDocumentString, collectGlob, collectCustomLoader, collectFallback],
    });
    for (const pointer in pointerOptionMap) {
        const pointerOptions = {
            ...((_a = pointerOptionMap[pointer]) !== null && _a !== void 0 ? _a : {}),
            unixify,
        };
        collect({
            pointer,
            pointerOptions,
            pointerOptionMap,
            options,
            addSource,
            addGlob,
            queue: queue.add,
        });
    }
    if (globs.length) {
        includeIgnored({
            options,
            globs,
        });
        const paths = await globby(globs, createGlobbyOptions(options));
        collectSourcesFromGlobals({
            filepaths: paths,
            options,
            globOptions,
            pointerOptionMap,
            addSource,
            queue: queue.add,
        });
    }
    await queue.runAll();
    return sources;
}
function collectSourcesSync({ pointerOptionMap, options, }) {
    var _a;
    const sources = [];
    const globs = [];
    const globOptions = {};
    const queue = useSyncQueue();
    const { addSource, addGlob, collect } = createHelpers({
        sources,
        globs,
        options,
        globOptions,
        stack: [collectDocumentString, collectGlob, collectCustomLoaderSync, collectFallbackSync],
    });
    for (const pointer in pointerOptionMap) {
        const pointerOptions = {
            ...((_a = pointerOptionMap[pointer]) !== null && _a !== void 0 ? _a : {}),
            unixify,
        };
        collect({
            pointer,
            pointerOptions,
            pointerOptionMap,
            options,
            addSource,
            addGlob,
            queue: queue.add,
        });
    }
    if (globs.length) {
        includeIgnored({
            options,
            globs,
        });
        const paths = sync(globs, createGlobbyOptions(options));
        collectSourcesFromGlobalsSync({
            filepaths: paths,
            options,
            globOptions,
            pointerOptionMap,
            addSource,
            queue: queue.add,
        });
    }
    queue.runAll();
    return sources;
}
//
function createHelpers({ sources, globs, options, globOptions, stack, }) {
    const addSource = ({ pointer, source, noCache, }) => {
        sources.push(source);
        if (!noCache) {
            options.cache[pointer] = source;
        }
    };
    const collect = useStack(...stack);
    const addGlob = ({ pointerOptions, pointer }) => {
        globs.push(pointer);
        Object.assign(globOptions, pointerOptions);
    };
    return {
        addSource,
        collect,
        addGlob,
    };
}
function includeIgnored({ options, globs }) {
    if (options.ignore) {
        const ignoreList = asArray(options.ignore)
            .map(g => `!(${g})`)
            .map(unixify);
        if (ignoreList.length > 0) {
            globs.push(...ignoreList);
        }
    }
}
function createGlobbyOptions(options) {
    return { absolute: true, ...options, ignore: [] };
}
function collectSourcesFromGlobals({ filepaths, options, globOptions, pointerOptionMap, addSource, queue, }) {
    const collectFromGlobs = useStack(collectCustomLoader, collectFallback);
    for (let i = 0; i < filepaths.length; i++) {
        const pointer = filepaths[i];
        collectFromGlobs({
            pointer,
            pointerOptions: globOptions,
            pointerOptionMap,
            options,
            addSource,
            addGlob: () => {
                throw new Error(`I don't accept any new globs!`);
            },
            queue,
        });
    }
}
function collectSourcesFromGlobalsSync({ filepaths, options, globOptions, pointerOptionMap, addSource, queue, }) {
    const collectFromGlobs = useStack(collectCustomLoaderSync, collectFallbackSync);
    for (let i = 0; i < filepaths.length; i++) {
        const pointer = filepaths[i];
        collectFromGlobs({
            pointer,
            pointerOptions: globOptions,
            pointerOptionMap,
            options,
            addSource,
            addGlob: () => {
                throw new Error(`I don't accept any new globs!`);
            },
            queue,
        });
    }
}
function addResultOfCustomLoader({ pointer, result, addSource, }) {
    if (isSchema(result)) {
        addSource({
            source: {
                location: pointer,
                schema: result,
                document: parse(printSchemaWithDirectives(result)),
            },
            pointer,
            noCache: true,
        });
    }
    else if (result.kind && result.kind === Kind.DOCUMENT) {
        addSource({
            source: {
                document: result,
                location: pointer,
            },
            pointer,
        });
    }
    else if (result.document) {
        addSource({
            source: {
                location: pointer,
                ...result,
            },
            pointer,
        });
    }
}
function collectDocumentString({ pointer, pointerOptions, options, addSource, queue }, next) {
    if (isDocumentString(pointer)) {
        return queue(() => {
            const source = parseGraphQLSDL(`${stringToHash(pointer)}.graphql`, pointer, {
                ...options,
                ...pointerOptions,
            });
            addSource({
                source,
                pointer,
            });
        });
    }
    next();
}
function collectGlob({ pointer, pointerOptions, addGlob }, next) {
    if (isGlob(pointerOptions.unixify(pointer))) {
        return addGlob({
            pointer: pointerOptions.unixify(pointer),
            pointerOptions,
        });
    }
    next();
}
function collectCustomLoader({ pointer, pointerOptions, queue, addSource, options, pointerOptionMap }, next) {
    if (pointerOptions.loader) {
        return queue(async () => {
            const loader = await useCustomLoader(pointerOptions.loader, options.cwd);
            const result = await loader(pointer, { ...options, ...pointerOptions }, pointerOptionMap);
            if (!result) {
                return;
            }
            addResultOfCustomLoader({ pointer, result, addSource });
        });
    }
    next();
}
function collectCustomLoaderSync({ pointer, pointerOptions, queue, addSource, options, pointerOptionMap }, next) {
    if (pointerOptions.loader) {
        return queue(() => {
            const loader = useCustomLoaderSync(pointerOptions.loader, options.cwd);
            const result = loader(pointer, { ...options, ...pointerOptions }, pointerOptionMap);
            if (result) {
                addResultOfCustomLoader({ pointer, result, addSource });
            }
        });
    }
    next();
}
function collectFallback({ queue, pointer, options, pointerOptions, addSource }) {
    return queue(async () => {
        const source = await loadFile(pointer, {
            ...options,
            ...pointerOptions,
        });
        if (source) {
            addSource({ source, pointer });
        }
    });
}
function collectFallbackSync({ queue, pointer, options, pointerOptions, addSource }) {
    return queue(() => {
        const source = loadFileSync(pointer, {
            ...options,
            ...pointerOptions,
        });
        if (source) {
            addSource({ source, pointer });
        }
    });
}

/**
 * @internal
 */
const filterKind = (content, filterKinds) => {
    if (content && content.definitions && content.definitions.length && filterKinds && filterKinds.length > 0) {
        const invalidDefinitions = [];
        const validDefinitions = [];
        for (const definitionNode of content.definitions) {
            if (filterKinds.includes(definitionNode.kind)) {
                invalidDefinitions.push(definitionNode);
            }
            else {
                validDefinitions.push(definitionNode);
            }
        }
        if (invalidDefinitions.length > 0) {
            invalidDefinitions.forEach(d => {
                debugLog(`Filtered document of kind ${d.kind} due to filter policy (${filterKinds.join(', ')})`);
            });
        }
        return {
            kind: Kind.DOCUMENT,
            definitions: validDefinitions,
        };
    }
    return content;
};

function parseSource({ partialSource, options, globOptions, pointerOptionMap, addValidSource }) {
    if (partialSource) {
        const input = prepareInput({
            source: partialSource,
            options,
            globOptions,
            pointerOptionMap,
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
function prepareInput({ source, options, globOptions, pointerOptionMap, }) {
    const specificOptions = {
        ...options,
        ...(source.location in pointerOptionMap ? globOptions : pointerOptionMap[source.location]),
    };
    return { source: { ...source }, options: specificOptions };
}
function parseSchema(input) {
    if (input.source.schema) {
        input.source.schema = fixSchemaAst(input.source.schema, input.options);
        input.source.rawSDL = printSchemaWithDirectives(input.source.schema, input.options);
    }
}
function parseRawSDL(input) {
    if (input.source.rawSDL) {
        input.source.document = parseGraphQLSDL(input.source.location, input.source.rawSDL, input.options).document;
    }
}
function useKindsFilter(input) {
    if (input.options.filterKinds) {
        input.source.document = filterKind(input.source.document, input.options.filterKinds);
    }
}
function useComments(input) {
    if (!input.source.rawSDL) {
        input.source.rawSDL = printWithComments(input.source.document);
        resetComments();
    }
}
function collectValidSources(input, addValidSource) {
    if (input.source.document.definitions && input.source.document.definitions.length > 0) {
        addValidSource(input.source);
    }
}

const CONCURRENCY_LIMIT$1 = 100;
/**
 * Asynchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
async function loadTypedefs(pointerOrPointers, options) {
    const pointerOptionMap = normalizePointers(pointerOrPointers);
    const globOptions = {};
    applyDefaultOptions(options);
    const sources = await collectSources({
        pointerOptionMap,
        options,
    });
    const validSources = [];
    // If we have few k of files it may be an issue
    const limit = useLimit(CONCURRENCY_LIMIT$1);
    await Promise.all(sources.map(partialSource => limit(() => parseSource({
        partialSource,
        options,
        globOptions,
        pointerOptionMap,
        addValidSource(source) {
            validSources.push(source);
        },
    }))));
    return prepareResult({ options, pointerOptionMap, validSources });
}
/**
 * Synchronously loads any GraphQL documents (i.e. executable documents like
 * operations and fragments as well as type system definitions) from the
 * provided pointers.
 * @param pointerOrPointers Pointers to the sources to load the documents from
 * @param options Additional options
 */
function loadTypedefsSync(pointerOrPointers, options) {
    const pointerOptionMap = normalizePointers(pointerOrPointers);
    const globOptions = {};
    applyDefaultOptions(options);
    const sources = collectSourcesSync({
        pointerOptionMap,
        options,
    });
    const validSources = [];
    sources.forEach(partialSource => {
        parseSource({
            partialSource,
            options,
            globOptions,
            pointerOptionMap,
            addValidSource(source) {
                validSources.push(source);
            },
        });
    });
    return prepareResult({ options, pointerOptionMap, validSources });
}
//
function prepareResult({ options, pointerOptionMap, validSources, }) {
    const pointerList = Object.keys(pointerOptionMap);
    if (pointerList.length > 0 && validSources.length === 0) {
        throw new Error(`
      Unable to find any GraphQL type definitions for the following pointers:
        ${pointerList.map(p => `
          - ${p}
          `)}`);
    }
    return options.sort
        ? validSources.sort((left, right) => compareStrings(left.location, right.location))
        : validSources;
}

/**
 * Kinds of AST nodes that are included in executable documents
 */
const OPERATION_KINDS = [Kind.OPERATION_DEFINITION, Kind.FRAGMENT_DEFINITION];
/**
 * Kinds of AST nodes that are included in type system definition documents
 */
const NON_OPERATION_KINDS = Object.keys(Kind)
    .reduce((prev, v) => [...prev, Kind[v]], [])
    .filter(v => !OPERATION_KINDS.includes(v));
/**
 * Asynchronously loads executable documents (i.e. operations and fragments) from
 * the provided pointers. The pointers may be individual files or a glob pattern.
 * The files themselves may be `.graphql` files or `.js` and `.ts` (in which
 * case they will be parsed using graphql-tag-pluck).
 * @param pointerOrPointers Pointers to the files to load the documents from
 * @param options Additional options
 */
function loadDocuments(pointerOrPointers, options) {
    return loadTypedefs(pointerOrPointers, { noRequire: true, filterKinds: NON_OPERATION_KINDS, ...options });
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
    return loadTypedefsSync(pointerOrPointers, { noRequire: true, filterKinds: NON_OPERATION_KINDS, ...options });
}

/**
 * Asynchronously loads a schema from the provided pointers.
 * @param schemaPointers Pointers to the sources to load the schema from
 * @param options Additional options
 */
async function loadSchema(schemaPointers, options) {
    const sources = await loadTypedefs(schemaPointers, {
        filterKinds: OPERATION_KINDS,
        ...options,
    });
    const { schemas, typeDefs } = collectSchemasAndTypeDefs(sources);
    const mergeSchemasOptions = {
        schemas,
        typeDefs,
        ...options,
    };
    const schema = await mergeSchemasAsync(mergeSchemasOptions);
    if (options === null || options === void 0 ? void 0 : options.includeSources) {
        includeSources(schema, sources);
    }
    return schema;
}
/**
 * Synchronously loads a schema from the provided pointers.
 * @param schemaPointers Pointers to the sources to load the schema from
 * @param options Additional options
 */
function loadSchemaSync(schemaPointers, options) {
    const sources = loadTypedefsSync(schemaPointers, {
        filterKinds: OPERATION_KINDS,
        ...options,
    });
    const { schemas, typeDefs } = collectSchemasAndTypeDefs(sources);
    const mergeSchemasOptions = {
        schemas,
        typeDefs,
        ...options,
    };
    const schema = mergeSchemas(mergeSchemasOptions);
    if (options === null || options === void 0 ? void 0 : options.includeSources) {
        includeSources(schema, sources);
    }
    return schema;
}
function includeSources(schema, sources) {
    schema.extensions = {
        ...schema.extensions,
        sources: sources
            .filter(source => source.rawSDL || source.document)
            .map(source => new Source(source.rawSDL || print(source.document), source.location)),
    };
}
function collectSchemasAndTypeDefs(sources) {
    const schemas = [];
    const typeDefs = [];
    sources.forEach(source => {
        if (source.schema) {
            schemas.push(source.schema);
        }
        else {
            typeDefs.push(source.document);
        }
    });
    return {
        schemas,
        typeDefs,
    };
}

export { NON_OPERATION_KINDS, OPERATION_KINDS, filterKind, loadDocuments, loadDocumentsSync, loadSchema, loadSchemaSync, loadTypedefs, loadTypedefsSync };
//# sourceMappingURL=index.esm.js.map
