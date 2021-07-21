'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

function _interopDefault (ex) { return (ex && (typeof ex === 'object') && 'default' in ex) ? ex['default'] : ex; }

const graphql = require('graphql');
const tslib = require('tslib');
const AggregateError = _interopDefault(require('@ardatan/aggregate-error'));
const camelCase = require('camel-case');

var asArray = function (fns) { return (Array.isArray(fns) ? fns : fns ? [fns] : []); };
function isEqual(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) {
            return false;
        }
        for (var index = 0; index < a.length; index++) {
            if (a[index] !== b[index]) {
                return false;
            }
        }
        return true;
    }
    return a === b || (!a && !b);
}
function isNotEqual(a, b) {
    return !isEqual(a, b);
}
function isDocumentString(str) {
    // XXX: is-valid-path or is-glob treat SDL as a valid path
    // (`scalar Date` for example)
    // this why checking the extension is fast enough
    // and prevent from parsing the string in order to find out
    // if the string is a SDL
    if (/\.[a-z0-9]+$/i.test(str)) {
        return false;
    }
    try {
        graphql.parse(str);
        return true;
    }
    catch (e) { }
    return false;
}
var invalidPathRegex = /[‘“!$%&^<=>`]/;
function isValidPath(str) {
    return typeof str === 'string' && !invalidPathRegex.test(str);
}
function compareStrings(a, b) {
    if (a.toString() < b.toString()) {
        return -1;
    }
    if (a.toString() > b.toString()) {
        return 1;
    }
    return 0;
}
function nodeToString(a) {
    if ('alias' in a) {
        return a.alias.value;
    }
    if ('name' in a) {
        return a.name.value;
    }
    return a.kind;
}
function compareNodes(a, b, customFn) {
    var aStr = nodeToString(a);
    var bStr = nodeToString(b);
    if (typeof customFn === 'function') {
        return customFn(aStr, bStr);
    }
    return compareStrings(aStr, bStr);
}

function debugLog() {
    var args = [];
    for (var _i = 0; _i < arguments.length; _i++) {
        args[_i] = arguments[_i];
    }
    if (process && process.env && process.env.DEBUG && !process.env.GQL_tools_NODEBUG) {
        // tslint:disable-next-line: no-console
        console.log.apply(console, tslib.__spread(args));
    }
}

var fixWindowsPath = function (path) { return path.replace(/\\/g, '/'); };

var flattenArray = function (arr) {
    return arr.reduce(function (acc, next) { return acc.concat(Array.isArray(next) ? flattenArray(next) : next); }, []);
};

var MAX_ARRAY_LENGTH = 10;
var MAX_RECURSIVE_DEPTH = 2;
/**
 * Used to print values in error messages.
 */
function inspect(value) {
    return formatValue(value, []);
}
function formatValue(value, seenValues) {
    switch (typeof value) {
        case 'string':
            return JSON.stringify(value);
        case 'function':
            return value.name ? "[function " + value.name + "]" : '[function]';
        case 'object':
            if (value === null) {
                return 'null';
            }
            return formatObjectValue(value, seenValues);
        default:
            return String(value);
    }
}
function formatObjectValue(value, previouslySeenValues) {
    if (previouslySeenValues.indexOf(value) !== -1) {
        return '[Circular]';
    }
    var seenValues = tslib.__spread(previouslySeenValues, [value]);
    var customInspectFn = getCustomFn(value);
    if (customInspectFn !== undefined) {
        var customValue = customInspectFn.call(value);
        // check for infinite recursion
        if (customValue !== value) {
            return typeof customValue === 'string' ? customValue : formatValue(customValue, seenValues);
        }
    }
    else if (Array.isArray(value)) {
        return formatArray(value, seenValues);
    }
    return formatObject(value, seenValues);
}
function formatObject(object, seenValues) {
    var keys = Object.keys(object);
    if (keys.length === 0) {
        return '{}';
    }
    if (seenValues.length > MAX_RECURSIVE_DEPTH) {
        return '[' + getObjectTag(object) + ']';
    }
    var properties = keys.map(function (key) {
        var value = formatValue(object[key], seenValues);
        return key + ': ' + value;
    });
    return '{ ' + properties.join(', ') + ' }';
}
function formatArray(array, seenValues) {
    if (array.length === 0) {
        return '[]';
    }
    if (seenValues.length > MAX_RECURSIVE_DEPTH) {
        return '[Array]';
    }
    var len = Math.min(MAX_ARRAY_LENGTH, array.length);
    var remaining = array.length - len;
    var items = [];
    for (var i = 0; i < len; ++i) {
        items.push(formatValue(array[i], seenValues));
    }
    if (remaining === 1) {
        items.push('... 1 more item');
    }
    else if (remaining > 1) {
        items.push("... " + remaining.toString(10) + " more items");
    }
    return '[' + items.join(', ') + ']';
}
function getCustomFn(obj) {
    if (typeof obj.inspect === 'function') {
        return obj.inspect;
    }
}
function getObjectTag(obj) {
    var tag = Object.prototype.toString
        .call(obj)
        .replace(/^\[object /, '')
        .replace(/]$/, '');
    if (tag === 'Object' && typeof obj.constructor === 'function') {
        var name_1 = obj.constructor.name;
        if (typeof name_1 === 'string' && name_1 !== '') {
            return name_1;
        }
    }
    return tag;
}

/**
 * Prepares an object map of argument values given a list of argument
 * definitions and list of argument AST nodes.
 *
 * Note: The returned value is a plain Object with a prototype, since it is
 * exposed to user code. Care should be taken to not pull values from the
 * Object prototype.
 */
function getArgumentValues(def, node, variableValues) {
    var e_1, _a;
    var _b;
    if (variableValues === void 0) { variableValues = {}; }
    var variableMap = Object.entries(variableValues).reduce(function (prev, _a) {
        var _b;
        var _c = tslib.__read(_a, 2), key = _c[0], value = _c[1];
        return (tslib.__assign(tslib.__assign({}, prev), (_b = {}, _b[key] = value, _b)));
    }, {});
    var coercedValues = {};
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    var argumentNodes = (_b = node.arguments) !== null && _b !== void 0 ? _b : [];
    var argNodeMap = argumentNodes.reduce(function (prev, arg) {
        var _a;
        return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[arg.name.value] = arg, _a)));
    }, {});
    try {
        for (var _c = tslib.__values(def.args), _d = _c.next(); !_d.done; _d = _c.next()) {
            var argDef = _d.value;
            var name_1 = argDef.name;
            var argType = argDef.type;
            var argumentNode = argNodeMap[name_1];
            if (!argumentNode) {
                if (argDef.defaultValue !== undefined) {
                    coercedValues[name_1] = argDef.defaultValue;
                }
                else if (graphql.isNonNullType(argType)) {
                    throw new graphql.GraphQLError("Argument \"" + name_1 + "\" of required type \"" + inspect(argType) + "\" " + 'was not provided.', node);
                }
                continue;
            }
            var valueNode = argumentNode.value;
            var isNull = valueNode.kind === graphql.Kind.NULL;
            if (valueNode.kind === graphql.Kind.VARIABLE) {
                var variableName = valueNode.name.value;
                if (variableValues == null || !(variableName in variableMap)) {
                    if (argDef.defaultValue !== undefined) {
                        coercedValues[name_1] = argDef.defaultValue;
                    }
                    else if (graphql.isNonNullType(argType)) {
                        throw new graphql.GraphQLError("Argument \"" + name_1 + "\" of required type \"" + inspect(argType) + "\" " +
                            ("was provided the variable \"$" + variableName + "\" which was not provided a runtime value."), valueNode);
                    }
                    continue;
                }
                isNull = variableValues[variableName] == null;
            }
            if (isNull && graphql.isNonNullType(argType)) {
                throw new graphql.GraphQLError("Argument \"" + name_1 + "\" of non-null type \"" + inspect(argType) + "\" " + 'must not be null.', valueNode);
            }
            var coercedValue = graphql.valueFromAST(valueNode, argType, variableValues);
            if (coercedValue === undefined) {
                // Note: ValuesOfCorrectTypeRule validation should catch this before
                // execution. This is a runtime check to ensure execution does not
                // continue with an invalid argument value.
                throw new graphql.GraphQLError("Argument \"" + name_1 + "\" has invalid value " + graphql.print(valueNode) + ".", valueNode);
            }
            coercedValues[name_1] = coercedValue;
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (_d && !_d.done && (_a = _c.return)) _a.call(_c);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return coercedValues;
}

function getDirectives(schema, node) {
    var schemaDirectives = schema && schema.getDirectives ? schema.getDirectives() : [];
    var schemaDirectiveMap = schemaDirectives.reduce(function (schemaDirectiveMap, schemaDirective) {
        schemaDirectiveMap[schemaDirective.name] = schemaDirective;
        return schemaDirectiveMap;
    }, {});
    var astNodes = [];
    if (node.astNode) {
        astNodes.push(node.astNode);
    }
    if ('extensionASTNodes' in node && node.extensionASTNodes) {
        astNodes = tslib.__spread(astNodes, node.extensionASTNodes);
    }
    var result = {};
    astNodes.forEach(function (astNode) {
        if (astNode.directives) {
            astNode.directives.forEach(function (directive) {
                var schemaDirective = schemaDirectiveMap[directive.name.value];
                if (schemaDirective) {
                    var directiveValue = getDirectiveValues(schemaDirective, astNode);
                    if (schemaDirective.isRepeatable) {
                        if (result[schemaDirective.name]) {
                            result[schemaDirective.name] = result[schemaDirective.name].concat([directiveValue]);
                        }
                        else {
                            result[schemaDirective.name] = [directiveValue];
                        }
                    }
                    else {
                        result[schemaDirective.name] = directiveValue;
                    }
                }
            });
        }
    });
    return result;
}
// graphql-js getDirectiveValues does not handle repeatable directives
function getDirectiveValues(directiveDef, node) {
    if (node.directives) {
        if (directiveDef.isRepeatable) {
            var directiveNodes = node.directives.filter(function (directive) { return directive.name.value === directiveDef.name; });
            return directiveNodes.map(function (directiveNode) { return getArgumentValues(directiveDef, directiveNode); });
        }
        var directiveNode = node.directives.find(function (directive) { return directive.name.value === directiveDef.name; });
        return getArgumentValues(directiveDef, directiveNode);
    }
}

function parseDirectiveValue(value) {
    switch (value.kind) {
        case graphql.Kind.INT:
            return parseInt(value.value);
        case graphql.Kind.FLOAT:
            return parseFloat(value.value);
        case graphql.Kind.BOOLEAN:
            return Boolean(value.value);
        case graphql.Kind.STRING:
        case graphql.Kind.ENUM:
            return value.value;
        case graphql.Kind.LIST:
            return value.values.map(function (v) { return parseDirectiveValue(v); });
        case graphql.Kind.OBJECT:
            return value.fields.reduce(function (prev, v) {
                var _a;
                return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[v.name.value] = parseDirectiveValue(v.value), _a)));
            }, {});
        case graphql.Kind.NULL:
            return null;
        default:
            return null;
    }
}
function getFieldsWithDirectives(documentNode, options) {
    var e_1, _a, e_2, _b;
    if (options === void 0) { options = {}; }
    var result = {};
    var selected = ['ObjectTypeDefinition', 'ObjectTypeExtension'];
    if (options.includeInputTypes) {
        selected = tslib.__spread(selected, ['InputObjectTypeDefinition', 'InputObjectTypeExtension']);
    }
    var allTypes = documentNode.definitions.filter(function (obj) { return selected.includes(obj.kind); });
    try {
        for (var allTypes_1 = tslib.__values(allTypes), allTypes_1_1 = allTypes_1.next(); !allTypes_1_1.done; allTypes_1_1 = allTypes_1.next()) {
            var type = allTypes_1_1.value;
            var typeName = type.name.value;
            try {
                for (var _c = (e_2 = void 0, tslib.__values(type.fields)), _d = _c.next(); !_d.done; _d = _c.next()) {
                    var field = _d.value;
                    if (field.directives && field.directives.length > 0) {
                        var fieldName = field.name.value;
                        var key = typeName + "." + fieldName;
                        var directives = field.directives.map(function (d) { return ({
                            name: d.name.value,
                            args: (d.arguments || []).reduce(function (prev, arg) {
                                var _a;
                                return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[arg.name.value] = parseDirectiveValue(arg.value), _a)));
                            }, {}),
                        }); });
                        result[key] = directives;
                    }
                }
            }
            catch (e_2_1) { e_2 = { error: e_2_1 }; }
            finally {
                try {
                    if (_d && !_d.done && (_b = _c.return)) _b.call(_c);
                }
                finally { if (e_2) throw e_2.error; }
            }
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (allTypes_1_1 && !allTypes_1_1.done && (_a = allTypes_1.return)) _a.call(allTypes_1);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return result;
}

function getImplementingTypes(interfaceName, schema) {
    var allTypesMap = schema.getTypeMap();
    var result = [];
    for (var graphqlTypeName in allTypesMap) {
        var graphqlType = allTypesMap[graphqlTypeName];
        if (graphql.isObjectType(graphqlType)) {
            var allInterfaces = graphqlType.getInterfaces();
            if (allInterfaces.find(function (int) { return int.name === interfaceName; })) {
                result.push(graphqlType.name);
            }
        }
    }
    return result;
}

function createSchemaDefinition(def, config) {
    var schemaRoot = {};
    if (def.query) {
        schemaRoot.query = def.query.toString();
    }
    if (def.mutation) {
        schemaRoot.mutation = def.mutation.toString();
    }
    if (def.subscription) {
        schemaRoot.subscription = def.subscription.toString();
    }
    var fields = Object.keys(schemaRoot)
        .map(function (rootType) { return (schemaRoot[rootType] ? rootType + ": " + schemaRoot[rootType] : null); })
        .filter(function (a) { return a; });
    if (fields.length) {
        return "schema { " + fields.join('\n') + " }";
    }
    if (config && config.force) {
        return " schema { query: Query } ";
    }
    return undefined;
}

function printSchemaWithDirectives(schema, _options) {
    var e_1, _a;
    var _b;
    var typesMap = schema.getTypeMap();
    var result = [getSchemaDefinition(schema)];
    for (var typeName in typesMap) {
        var type = typesMap[typeName];
        var isPredefinedScalar = graphql.isScalarType(type) && graphql.isSpecifiedScalarType(type);
        var isIntrospection = graphql.isIntrospectionType(type);
        if (isPredefinedScalar || isIntrospection) {
            continue;
        }
        // KAMIL: we might want to turn on descriptions in future
        result.push(graphql.print((_b = correctType(typeName, typesMap)) === null || _b === void 0 ? void 0 : _b.astNode));
    }
    var directives = schema.getDirectives();
    try {
        for (var directives_1 = tslib.__values(directives), directives_1_1 = directives_1.next(); !directives_1_1.done; directives_1_1 = directives_1.next()) {
            var directive = directives_1_1.value;
            if (directive.astNode) {
                result.push(graphql.print(directive.astNode));
            }
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (directives_1_1 && !directives_1_1.done && (_a = directives_1.return)) _a.call(directives_1);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return result.join('\n');
}
function extendDefinition(type) {
    switch (type.astNode.kind) {
        case graphql.Kind.OBJECT_TYPE_DEFINITION:
            return tslib.__assign(tslib.__assign({}, type.astNode), { fields: type.astNode.fields.concat(type.extensionASTNodes.reduce(function (fields, node) { return fields.concat(node.fields); }, [])) });
        case graphql.Kind.INPUT_OBJECT_TYPE_DEFINITION:
            return tslib.__assign(tslib.__assign({}, type.astNode), { fields: type.astNode.fields.concat(type.extensionASTNodes.reduce(function (fields, node) { return fields.concat(node.fields); }, [])) });
        default:
            return type.astNode;
    }
}
function correctType(typeName, typesMap) {
    var e_2, _a, e_3, _b;
    var type = typesMap[typeName];
    type.name = typeName.toString();
    if (type.astNode && type.extensionASTNodes) {
        type.astNode = type.extensionASTNodes ? extendDefinition(type) : type.astNode;
    }
    var doc = graphql.parse(graphql.printType(type));
    var fixedAstNode = doc.definitions[0];
    var originalAstNode = type === null || type === void 0 ? void 0 : type.astNode;
    if (originalAstNode) {
        fixedAstNode.directives = originalAstNode === null || originalAstNode === void 0 ? void 0 : originalAstNode.directives;
        if (fixedAstNode && 'fields' in fixedAstNode && originalAstNode && 'fields' in originalAstNode) {
            var _loop_1 = function (fieldDefinitionNode) {
                var e_4, _a;
                var originalFieldDefinitionNode = originalAstNode.fields.find(function (field) { return field.name.value === fieldDefinitionNode.name.value; });
                fieldDefinitionNode.directives = originalFieldDefinitionNode === null || originalFieldDefinitionNode === void 0 ? void 0 : originalFieldDefinitionNode.directives;
                if (fieldDefinitionNode &&
                    'arguments' in fieldDefinitionNode &&
                    originalFieldDefinitionNode &&
                    'arguments' in originalFieldDefinitionNode) {
                    var _loop_3 = function (argument) {
                        var originalArgumentNode = (_c = originalFieldDefinitionNode.arguments) === null || _c === void 0 ? void 0 : _c.find(function (arg) { return arg.name.value === argument.name.value; });
                        argument.directives = originalArgumentNode.directives;
                    };
                    try {
                        for (var _b = (e_4 = void 0, tslib.__values(fieldDefinitionNode.arguments)), _c = _b.next(); !_c.done; _c = _b.next()) {
                            var argument = _c.value;
                            _loop_3(argument);
                        }
                    }
                    catch (e_4_1) { e_4 = { error: e_4_1 }; }
                    finally {
                        try {
                            if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
                        }
                        finally { if (e_4) throw e_4.error; }
                    }
                }
            };
            try {
                for (var _d = tslib.__values(fixedAstNode.fields), _e = _d.next(); !_e.done; _e = _d.next()) {
                    var fieldDefinitionNode = _e.value;
                    _loop_1(fieldDefinitionNode);
                }
            }
            catch (e_2_1) { e_2 = { error: e_2_1 }; }
            finally {
                try {
                    if (_e && !_e.done && (_a = _d.return)) _a.call(_d);
                }
                finally { if (e_2) throw e_2.error; }
            }
        }
        else if (fixedAstNode && 'values' in fixedAstNode && originalAstNode && 'values' in originalAstNode) {
            var _loop_2 = function (valueDefinitionNode) {
                var originalValueDefinitionNode = originalAstNode.values.find(function (valueNode) { return valueNode.name.value === valueDefinitionNode.name.value; });
                valueDefinitionNode.directives = originalValueDefinitionNode === null || originalValueDefinitionNode === void 0 ? void 0 : originalValueDefinitionNode.directives;
            };
            try {
                for (var _f = tslib.__values(fixedAstNode.values), _g = _f.next(); !_g.done; _g = _f.next()) {
                    var valueDefinitionNode = _g.value;
                    _loop_2(valueDefinitionNode);
                }
            }
            catch (e_3_1) { e_3 = { error: e_3_1 }; }
            finally {
                try {
                    if (_g && !_g.done && (_b = _f.return)) _b.call(_f);
                }
                finally { if (e_3) throw e_3.error; }
            }
        }
    }
    type.astNode = fixedAstNode;
    return type;
}
function getSchemaDefinition(schema) {
    if (!Object.getOwnPropertyDescriptor(schema, 'astNode').get && schema.astNode) {
        return graphql.print(schema.astNode);
    }
    else {
        return createSchemaDefinition({
            query: schema.getQueryType(),
            mutation: schema.getMutationType(),
            subscription: schema.getSubscriptionType(),
        });
    }
}

function validateGraphQlDocuments(schema, documentFiles, effectiveRules) {
    return tslib.__awaiter(this, void 0, void 0, function () {
        var allFragments, allErrors;
        var _this = this;
        return tslib.__generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    effectiveRules = effectiveRules || createDefaultRules();
                    allFragments = [];
                    documentFiles.forEach(function (documentFile) {
                        var e_1, _a;
                        if (documentFile.document) {
                            try {
                                for (var _b = tslib.__values(documentFile.document.definitions), _c = _b.next(); !_c.done; _c = _b.next()) {
                                    var definitionNode = _c.value;
                                    if (definitionNode.kind === graphql.Kind.FRAGMENT_DEFINITION) {
                                        allFragments.push(definitionNode);
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
                        }
                    });
                    allErrors = [];
                    return [4 /*yield*/, Promise.all(documentFiles.map(function (documentFile) { return tslib.__awaiter(_this, void 0, void 0, function () {
                            var documentToValidate, errors;
                            return tslib.__generator(this, function (_a) {
                                documentToValidate = {
                                    kind: graphql.Kind.DOCUMENT,
                                    definitions: tslib.__spread(allFragments, documentFile.document.definitions).filter(function (definition, index, list) {
                                        if (definition.kind === graphql.Kind.FRAGMENT_DEFINITION) {
                                            var firstIndex = list.findIndex(function (def) { return def.kind === graphql.Kind.FRAGMENT_DEFINITION && def.name.value === definition.name.value; });
                                            var isDuplicated = firstIndex !== index;
                                            if (isDuplicated) {
                                                return false;
                                            }
                                        }
                                        return true;
                                    }),
                                };
                                errors = graphql.validate(schema, documentToValidate, effectiveRules);
                                if (errors.length > 0) {
                                    allErrors.push({
                                        filePath: documentFile.location,
                                        errors: errors,
                                    });
                                }
                                return [2 /*return*/];
                            });
                        }); }))];
                case 1:
                    _a.sent();
                    return [2 /*return*/, allErrors];
            }
        });
    });
}
function checkValidationErrors(loadDocumentErrors) {
    var e_2, _a;
    if (loadDocumentErrors.length > 0) {
        var errors = [];
        var _loop_1 = function (loadDocumentError) {
            var e_3, _a;
            var _loop_2 = function (graphQLError) {
                var error = new Error();
                error.name = 'GraphQLDocumentError';
                error.message = error.name + ": " + graphQLError.message;
                error.stack = error.message;
                graphQLError.locations.forEach(function (location) { return (error.stack += "\n    at " + loadDocumentError.filePath + ":" + location.line + ":" + location.column); });
                errors.push(error);
            };
            try {
                for (var _b = (e_3 = void 0, tslib.__values(loadDocumentError.errors)), _c = _b.next(); !_c.done; _c = _b.next()) {
                    var graphQLError = _c.value;
                    _loop_2(graphQLError);
                }
            }
            catch (e_3_1) { e_3 = { error: e_3_1 }; }
            finally {
                try {
                    if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
                }
                finally { if (e_3) throw e_3.error; }
            }
        };
        try {
            for (var loadDocumentErrors_1 = tslib.__values(loadDocumentErrors), loadDocumentErrors_1_1 = loadDocumentErrors_1.next(); !loadDocumentErrors_1_1.done; loadDocumentErrors_1_1 = loadDocumentErrors_1.next()) {
                var loadDocumentError = loadDocumentErrors_1_1.value;
                _loop_1(loadDocumentError);
            }
        }
        catch (e_2_1) { e_2 = { error: e_2_1 }; }
        finally {
            try {
                if (loadDocumentErrors_1_1 && !loadDocumentErrors_1_1.done && (_a = loadDocumentErrors_1.return)) _a.call(loadDocumentErrors_1);
            }
            finally { if (e_2) throw e_2.error; }
        }
        throw new AggregateError(errors);
    }
}
function createDefaultRules() {
    var ignored = ['NoUnusedFragmentsRule', 'NoUnusedVariablesRule', 'KnownDirectivesRule'];
    // GraphQL v14 has no Rule suffix in function names
    // Adding `*Rule` makes validation backwards compatible
    ignored.forEach(function (rule) {
        ignored.push(rule.replace(/Rule$/, ''));
    });
    return graphql.specifiedRules.filter(function (f) { return !ignored.includes(f.name); });
}

function buildFixedSchema(schema, options) {
    return graphql.buildSchema(printSchemaWithDirectives(schema), tslib.__assign({ noLocation: true }, (options || {})));
}
function fixSchemaAst(schema, options) {
    var schemaWithValidAst;
    if (!schema.astNode) {
        Object.defineProperty(schema, 'astNode', {
            get: function () {
                if (!schemaWithValidAst) {
                    schemaWithValidAst = buildFixedSchema(schema, options);
                }
                return schemaWithValidAst.astNode;
            },
        });
    }
    if (!schema.extensionASTNodes) {
        Object.defineProperty(schema, 'extensionASTNodes', {
            get: function () {
                if (!schemaWithValidAst) {
                    schemaWithValidAst = buildFixedSchema(schema, options);
                }
                return schemaWithValidAst.extensionASTNodes;
            },
        });
    }
    return schema;
}

/**
 * Produces the value of a block string from its parsed raw value, similar to
 * CoffeeScript's block string, Python's docstring trim or Ruby's strip_heredoc.
 *
 * This implements the GraphQL spec's BlockStringValue() static algorithm.
 *
 * @internal
 */
function dedentBlockStringValue(rawString) {
  // Expand a block string's raw value into independent lines.
  var lines = rawString.split(/\r\n|[\n\r]/g); // Remove common indentation from all lines but first.

  var commonIndent = getBlockStringIndentation(lines);

  if (commonIndent !== 0) {
    for (var i = 1; i < lines.length; i++) {
      lines[i] = lines[i].slice(commonIndent);
    }
  } // Remove leading and trailing blank lines.


  while (lines.length > 0 && isBlank(lines[0])) {
    lines.shift();
  }

  while (lines.length > 0 && isBlank(lines[lines.length - 1])) {
    lines.pop();
  } // Return a string of the lines joined with U+000A.


  return lines.join('\n');
}
/**
 * @internal
 */

function getBlockStringIndentation(lines) {
  var commonIndent = null;

  for (var i = 1; i < lines.length; i++) {
    var line = lines[i];
    var indent = leadingWhitespace(line);

    if (indent === line.length) {
      continue; // skip empty lines
    }

    if (commonIndent === null || indent < commonIndent) {
      commonIndent = indent;

      if (commonIndent === 0) {
        break;
      }
    }
  }

  return commonIndent === null ? 0 : commonIndent;
}

function leadingWhitespace(str) {
  var i = 0;

  while (i < str.length && (str[i] === ' ' || str[i] === '\t')) {
    i++;
  }

  return i;
}

function isBlank(str) {
  return leadingWhitespace(str) === str.length;
}

function parseGraphQLSDL(location, rawSDL, options) {
    if (options === void 0) { options = {}; }
    var document;
    var sdl = rawSDL;
    var sdlModified = false;
    try {
        if (options.commentDescriptions && sdl.includes('#')) {
            sdlModified = true;
            document = transformCommentsToDescriptions(rawSDL, options);
            // If noLocation=true, we need to make sure to print and parse it again, to remove locations,
            // since `transformCommentsToDescriptions` must have locations set in order to transform the comments
            // into descriptions.
            if (options.noLocation) {
                document = graphql.parse(graphql.print(document), options);
            }
        }
        else {
            document = graphql.parse(new graphql.Source(sdl, location), options);
        }
    }
    catch (e) {
        if (e.message.includes('EOF')) {
            document = {
                kind: graphql.Kind.DOCUMENT,
                definitions: [],
            };
        }
        else {
            throw e;
        }
    }
    return {
        location: location,
        document: document,
        rawSDL: sdlModified ? graphql.print(document) : sdl,
    };
}
function getLeadingCommentBlock(node) {
    var loc = node.loc;
    if (!loc) {
        return;
    }
    var comments = [];
    var token = loc.startToken.prev;
    while (token != null &&
        token.kind === graphql.TokenKind.COMMENT &&
        token.next &&
        token.prev &&
        token.line + 1 === token.next.line &&
        token.line !== token.prev.line) {
        var value = String(token.value);
        comments.push(value);
        token = token.prev;
    }
    return comments.length > 0 ? comments.reverse().join('\n') : undefined;
}
function transformCommentsToDescriptions(sourceSdl, options) {
    if (options === void 0) { options = {}; }
    var parsedDoc = graphql.parse(sourceSdl, tslib.__assign(tslib.__assign({}, options), { noLocation: false }));
    var modifiedDoc = graphql.visit(parsedDoc, {
        leave: function (node) {
            if (isDescribable(node)) {
                var rawValue = getLeadingCommentBlock(node);
                if (rawValue !== undefined) {
                    var commentsBlock = dedentBlockStringValue('\n' + rawValue);
                    var isBlock = commentsBlock.includes('\n');
                    if (!node.description) {
                        return tslib.__assign(tslib.__assign({}, node), { description: {
                                kind: graphql.Kind.STRING,
                                value: commentsBlock,
                                block: isBlock,
                            } });
                    }
                    else {
                        return tslib.__assign(tslib.__assign({}, node), { description: tslib.__assign(tslib.__assign({}, node.description), { value: node.description.value + '\n' + commentsBlock, block: true }) });
                    }
                }
            }
        },
    });
    return modifiedDoc;
}
function isDescribable(node) {
    return (graphql.isTypeSystemDefinitionNode(node) ||
        node.kind === graphql.Kind.FIELD_DEFINITION ||
        node.kind === graphql.Kind.INPUT_VALUE_DEFINITION ||
        node.kind === graphql.Kind.ENUM_VALUE_DEFINITION);
}

function stripBOM(content) {
    content = content.toString();
    // Remove byte order marker. This catches EF BB BF (the UTF-8 BOM)
    // because the buffer-to-string conversion in `fs.readFileSync()`
    // translates it to FEFF, the UTF-16 BOM.
    if (content.charCodeAt(0) === 0xfeff) {
        content = content.slice(1);
    }
    return content;
}
function parseBOM(content) {
    return JSON.parse(stripBOM(content));
}
function parseGraphQLJSON(location, jsonContent, options) {
    var parsedJson = parseBOM(jsonContent);
    if (parsedJson.data) {
        parsedJson = parsedJson.data;
    }
    if (parsedJson.kind === 'Document') {
        var document_1 = parsedJson;
        return {
            location: location,
            document: document_1,
        };
    }
    else if (parsedJson.__schema) {
        var schema = graphql.buildClientSchema(parsedJson, options);
        var rawSDL = printSchemaWithDirectives(schema);
        return {
            location: location,
            document: parseGraphQLSDL(location, rawSDL, options).document,
            rawSDL: rawSDL,
            schema: schema,
        };
    }
    throw new Error("Not valid JSON content");
}

/**
 * Get all GraphQL types from schema without:
 *
 * - Query, Mutation, Subscription objects
 * - Internal scalars added by parser
 *
 * @param schema
 */
function getUserTypesFromSchema(schema) {
    var allTypesMap = schema.getTypeMap();
    // tslint:disable-next-line: no-unnecessary-local-variable
    var modelTypes = Object.values(allTypesMap).filter(function (graphqlType) {
        if (graphql.isObjectType(graphqlType)) {
            // Filter out private types
            if (graphqlType.name.startsWith('__')) {
                return false;
            }
            if (schema.getMutationType() && graphqlType.name === schema.getMutationType().name) {
                return false;
            }
            if (schema.getQueryType() && graphqlType.name === schema.getQueryType().name) {
                return false;
            }
            if (schema.getSubscriptionType() && graphqlType.name === schema.getSubscriptionType().name) {
                return false;
            }
            return true;
        }
        return false;
    });
    return modelTypes;
}

var operationVariables = [];
var fieldTypeMap = new Map();
function addOperationVariable(variable) {
    operationVariables.push(variable);
}
function resetOperationVariables() {
    operationVariables = [];
}
function resetFieldMap() {
    fieldTypeMap = new Map();
}
function buildOperationName(name) {
    return camelCase.camelCase(name);
}
function buildOperationNodeForField(_a) {
    var schema = _a.schema, kind = _a.kind, field = _a.field, models = _a.models, ignore = _a.ignore, depthLimit = _a.depthLimit, circularReferenceDepth = _a.circularReferenceDepth, argNames = _a.argNames, _b = _a.selectedFields, selectedFields = _b === void 0 ? true : _b;
    resetOperationVariables();
    resetFieldMap();
    var operationNode = buildOperationAndCollectVariables({
        schema: schema,
        fieldName: field,
        kind: kind,
        models: models || [],
        ignore: ignore || [],
        depthLimit: depthLimit || Infinity,
        circularReferenceDepth: circularReferenceDepth || 1,
        argNames: argNames,
        selectedFields: selectedFields,
    });
    // attach variables
    operationNode.variableDefinitions = tslib.__spread(operationVariables);
    resetOperationVariables();
    resetFieldMap();
    return operationNode;
}
function buildOperationAndCollectVariables(_a) {
    var schema = _a.schema, fieldName = _a.fieldName, kind = _a.kind, models = _a.models, ignore = _a.ignore, depthLimit = _a.depthLimit, circularReferenceDepth = _a.circularReferenceDepth, argNames = _a.argNames, selectedFields = _a.selectedFields;
    var typeMap = {
        query: schema.getQueryType(),
        mutation: schema.getMutationType(),
        subscription: schema.getSubscriptionType(),
    };
    var type = typeMap[kind];
    var field = type.getFields()[fieldName];
    var operationName = buildOperationName(fieldName + "_" + kind);
    if (field.args) {
        field.args.forEach(function (arg) {
            var argName = arg.name;
            if (!argNames || argNames.includes(argName)) {
                addOperationVariable(resolveVariable(arg, argName));
            }
        });
    }
    return {
        kind: graphql.Kind.OPERATION_DEFINITION,
        operation: kind,
        name: {
            kind: 'Name',
            value: operationName,
        },
        variableDefinitions: [],
        selectionSet: {
            kind: graphql.Kind.SELECTION_SET,
            selections: [
                resolveField({
                    type: type,
                    field: field,
                    models: models,
                    firstCall: true,
                    path: [],
                    ancestors: [],
                    ignore: ignore,
                    depthLimit: depthLimit,
                    circularReferenceDepth: circularReferenceDepth,
                    schema: schema,
                    depth: 0,
                    argNames: argNames,
                    selectedFields: selectedFields,
                }),
            ],
        },
    };
}
function resolveSelectionSet(_a) {
    var parent = _a.parent, type = _a.type, models = _a.models, firstCall = _a.firstCall, path = _a.path, ancestors = _a.ancestors, ignore = _a.ignore, depthLimit = _a.depthLimit, circularReferenceDepth = _a.circularReferenceDepth, schema = _a.schema, depth = _a.depth, argNames = _a.argNames, selectedFields = _a.selectedFields;
    if (typeof selectedFields === 'boolean' && depth > depthLimit) {
        return;
    }
    if (graphql.isUnionType(type)) {
        var types = type.getTypes();
        return {
            kind: graphql.Kind.SELECTION_SET,
            selections: types
                .filter(function (t) {
                return !hasCircularRef(tslib.__spread(ancestors, [t]), {
                    depth: circularReferenceDepth,
                });
            })
                .map(function (t) {
                return {
                    kind: graphql.Kind.INLINE_FRAGMENT,
                    typeCondition: {
                        kind: graphql.Kind.NAMED_TYPE,
                        name: {
                            kind: graphql.Kind.NAME,
                            value: t.name,
                        },
                    },
                    selectionSet: resolveSelectionSet({
                        parent: type,
                        type: t,
                        models: models,
                        path: path,
                        ancestors: ancestors,
                        ignore: ignore,
                        depthLimit: depthLimit,
                        circularReferenceDepth: circularReferenceDepth,
                        schema: schema,
                        depth: depth,
                        argNames: argNames,
                        selectedFields: selectedFields,
                    }),
                };
            })
                .filter(function (fragmentNode) { var _a, _b; return ((_b = (_a = fragmentNode === null || fragmentNode === void 0 ? void 0 : fragmentNode.selectionSet) === null || _a === void 0 ? void 0 : _a.selections) === null || _b === void 0 ? void 0 : _b.length) > 0; }),
        };
    }
    if (graphql.isInterfaceType(type)) {
        var types = Object.values(schema.getTypeMap()).filter(function (t) { return graphql.isObjectType(t) && t.getInterfaces().includes(type); });
        return {
            kind: graphql.Kind.SELECTION_SET,
            selections: types
                .filter(function (t) {
                return !hasCircularRef(tslib.__spread(ancestors, [t]), {
                    depth: circularReferenceDepth,
                });
            })
                .map(function (t) {
                return {
                    kind: graphql.Kind.INLINE_FRAGMENT,
                    typeCondition: {
                        kind: graphql.Kind.NAMED_TYPE,
                        name: {
                            kind: graphql.Kind.NAME,
                            value: t.name,
                        },
                    },
                    selectionSet: resolveSelectionSet({
                        parent: type,
                        type: t,
                        models: models,
                        path: path,
                        ancestors: ancestors,
                        ignore: ignore,
                        depthLimit: depthLimit,
                        circularReferenceDepth: circularReferenceDepth,
                        schema: schema,
                        depth: depth,
                        argNames: argNames,
                        selectedFields: selectedFields,
                    }),
                };
            })
                .filter(function (fragmentNode) { var _a, _b; return ((_b = (_a = fragmentNode === null || fragmentNode === void 0 ? void 0 : fragmentNode.selectionSet) === null || _a === void 0 ? void 0 : _a.selections) === null || _b === void 0 ? void 0 : _b.length) > 0; }),
        };
    }
    if (graphql.isObjectType(type)) {
        var isIgnored = ignore.includes(type.name) || ignore.includes(parent.name + "." + path[path.length - 1]);
        var isModel = models.includes(type.name);
        if (!firstCall && isModel && !isIgnored) {
            return {
                kind: graphql.Kind.SELECTION_SET,
                selections: [
                    {
                        kind: graphql.Kind.FIELD,
                        name: {
                            kind: graphql.Kind.NAME,
                            value: 'id',
                        },
                    },
                ],
            };
        }
        var fields_1 = type.getFields();
        return {
            kind: graphql.Kind.SELECTION_SET,
            selections: Object.keys(fields_1)
                .filter(function (fieldName) {
                return !hasCircularRef(tslib.__spread(ancestors, [graphql.getNamedType(fields_1[fieldName].type)]), {
                    depth: circularReferenceDepth,
                });
            })
                .map(function (fieldName) {
                var selectedSubFields = typeof selectedFields === 'object' ? selectedFields[fieldName] : true;
                if (selectedSubFields) {
                    return resolveField({
                        type: type,
                        field: fields_1[fieldName],
                        models: models,
                        path: tslib.__spread(path, [fieldName]),
                        ancestors: ancestors,
                        ignore: ignore,
                        depthLimit: depthLimit,
                        circularReferenceDepth: circularReferenceDepth,
                        schema: schema,
                        depth: depth,
                        argNames: argNames,
                        selectedFields: selectedSubFields,
                    });
                }
            })
                .filter(function (f) {
                var _a, _b;
                if (f) {
                    if ('selectionSet' in f) {
                        return (_b = (_a = f.selectionSet) === null || _a === void 0 ? void 0 : _a.selections) === null || _b === void 0 ? void 0 : _b.length;
                    }
                    else {
                        return true;
                    }
                }
                return false;
            }),
        };
    }
}
function resolveVariable(arg, name) {
    function resolveVariableType(type) {
        if (graphql.isListType(type)) {
            return {
                kind: graphql.Kind.LIST_TYPE,
                type: resolveVariableType(type.ofType),
            };
        }
        if (graphql.isNonNullType(type)) {
            return {
                kind: graphql.Kind.NON_NULL_TYPE,
                type: resolveVariableType(type.ofType),
            };
        }
        return {
            kind: graphql.Kind.NAMED_TYPE,
            name: {
                kind: graphql.Kind.NAME,
                value: type.name,
            },
        };
    }
    return {
        kind: graphql.Kind.VARIABLE_DEFINITION,
        variable: {
            kind: graphql.Kind.VARIABLE,
            name: {
                kind: graphql.Kind.NAME,
                value: name || arg.name,
            },
        },
        type: resolveVariableType(arg.type),
    };
}
function getArgumentName(name, path) {
    return camelCase.camelCase(tslib.__spread(path, [name]).join('_'));
}
function resolveField(_a) {
    var type = _a.type, field = _a.field, models = _a.models, firstCall = _a.firstCall, path = _a.path, ancestors = _a.ancestors, ignore = _a.ignore, depthLimit = _a.depthLimit, circularReferenceDepth = _a.circularReferenceDepth, schema = _a.schema, depth = _a.depth, argNames = _a.argNames, selectedFields = _a.selectedFields;
    var namedType = graphql.getNamedType(field.type);
    var args = [];
    var removeField = false;
    if (field.args && field.args.length) {
        args = field.args
            .map(function (arg) {
            var argumentName = getArgumentName(arg.name, path);
            if (argNames && !argNames.includes(argumentName)) {
                if (graphql.isNonNullType(arg.type)) {
                    removeField = true;
                }
                return null;
            }
            if (!firstCall) {
                addOperationVariable(resolveVariable(arg, argumentName));
            }
            return {
                kind: graphql.Kind.ARGUMENT,
                name: {
                    kind: graphql.Kind.NAME,
                    value: arg.name,
                },
                value: {
                    kind: graphql.Kind.VARIABLE,
                    name: {
                        kind: graphql.Kind.NAME,
                        value: getArgumentName(arg.name, path),
                    },
                },
            };
        })
            .filter(Boolean);
    }
    if (removeField) {
        return null;
    }
    var fieldPath = tslib.__spread(path, [field.name]);
    var fieldPathStr = fieldPath.join('.');
    var fieldName = field.name;
    if (fieldTypeMap.has(fieldPathStr) && fieldTypeMap.get(fieldPathStr) !== field.type.toString()) {
        fieldName += field.type.toString().replace('!', 'NonNull');
    }
    fieldTypeMap.set(fieldPathStr, field.type.toString());
    if (!graphql.isScalarType(namedType) && !graphql.isEnumType(namedType)) {
        return tslib.__assign(tslib.__assign({ kind: graphql.Kind.FIELD, name: {
                kind: graphql.Kind.NAME,
                value: field.name,
            } }, (fieldName !== field.name && { alias: { kind: graphql.Kind.NAME, value: fieldName } })), { selectionSet: resolveSelectionSet({
                parent: type,
                type: namedType,
                models: models,
                firstCall: firstCall,
                path: fieldPath,
                ancestors: tslib.__spread(ancestors, [type]),
                ignore: ignore,
                depthLimit: depthLimit,
                circularReferenceDepth: circularReferenceDepth,
                schema: schema,
                depth: depth + 1,
                argNames: argNames,
                selectedFields: selectedFields,
            }) || undefined, arguments: args });
    }
    return tslib.__assign(tslib.__assign({ kind: graphql.Kind.FIELD, name: {
            kind: graphql.Kind.NAME,
            value: field.name,
        } }, (fieldName !== field.name && { alias: { kind: graphql.Kind.NAME, value: fieldName } })), { arguments: args });
}
function hasCircularRef(types, config) {
    if (config === void 0) { config = {
        depth: 1,
    }; }
    var type = types[types.length - 1];
    if (graphql.isScalarType(type)) {
        return false;
    }
    var size = types.filter(function (t) { return t.name === type.name; }).length;
    return size > config.depth;
}

(function (VisitSchemaKind) {
    VisitSchemaKind["TYPE"] = "VisitSchemaKind.TYPE";
    VisitSchemaKind["SCALAR_TYPE"] = "VisitSchemaKind.SCALAR_TYPE";
    VisitSchemaKind["ENUM_TYPE"] = "VisitSchemaKind.ENUM_TYPE";
    VisitSchemaKind["COMPOSITE_TYPE"] = "VisitSchemaKind.COMPOSITE_TYPE";
    VisitSchemaKind["OBJECT_TYPE"] = "VisitSchemaKind.OBJECT_TYPE";
    VisitSchemaKind["INPUT_OBJECT_TYPE"] = "VisitSchemaKind.INPUT_OBJECT_TYPE";
    VisitSchemaKind["ABSTRACT_TYPE"] = "VisitSchemaKind.ABSTRACT_TYPE";
    VisitSchemaKind["UNION_TYPE"] = "VisitSchemaKind.UNION_TYPE";
    VisitSchemaKind["INTERFACE_TYPE"] = "VisitSchemaKind.INTERFACE_TYPE";
    VisitSchemaKind["ROOT_OBJECT"] = "VisitSchemaKind.ROOT_OBJECT";
    VisitSchemaKind["QUERY"] = "VisitSchemaKind.QUERY";
    VisitSchemaKind["MUTATION"] = "VisitSchemaKind.MUTATION";
    VisitSchemaKind["SUBSCRIPTION"] = "VisitSchemaKind.SUBSCRIPTION";
})(exports.VisitSchemaKind || (exports.VisitSchemaKind = {}));
(function (MapperKind) {
    MapperKind["TYPE"] = "MapperKind.TYPE";
    MapperKind["SCALAR_TYPE"] = "MapperKind.SCALAR_TYPE";
    MapperKind["ENUM_TYPE"] = "MapperKind.ENUM_TYPE";
    MapperKind["COMPOSITE_TYPE"] = "MapperKind.COMPOSITE_TYPE";
    MapperKind["OBJECT_TYPE"] = "MapperKind.OBJECT_TYPE";
    MapperKind["INPUT_OBJECT_TYPE"] = "MapperKind.INPUT_OBJECT_TYPE";
    MapperKind["ABSTRACT_TYPE"] = "MapperKind.ABSTRACT_TYPE";
    MapperKind["UNION_TYPE"] = "MapperKind.UNION_TYPE";
    MapperKind["INTERFACE_TYPE"] = "MapperKind.INTERFACE_TYPE";
    MapperKind["ROOT_OBJECT"] = "MapperKind.ROOT_OBJECT";
    MapperKind["QUERY"] = "MapperKind.QUERY";
    MapperKind["MUTATION"] = "MapperKind.MUTATION";
    MapperKind["SUBSCRIPTION"] = "MapperKind.SUBSCRIPTION";
    MapperKind["DIRECTIVE"] = "MapperKind.DIRECTIVE";
    MapperKind["FIELD"] = "MapperKind.FIELD";
    MapperKind["COMPOSITE_FIELD"] = "MapperKind.COMPOSITE_FIELD";
    MapperKind["OBJECT_FIELD"] = "MapperKind.OBJECT_FIELD";
    MapperKind["ROOT_FIELD"] = "MapperKind.ROOT_FIELD";
    MapperKind["QUERY_ROOT_FIELD"] = "MapperKind.QUERY_ROOT_FIELD";
    MapperKind["MUTATION_ROOT_FIELD"] = "MapperKind.MUTATION_ROOT_FIELD";
    MapperKind["SUBSCRIPTION_ROOT_FIELD"] = "MapperKind.SUBSCRIPTION_ROOT_FIELD";
    MapperKind["INTERFACE_FIELD"] = "MapperKind.INTERFACE_FIELD";
    MapperKind["INPUT_OBJECT_FIELD"] = "MapperKind.INPUT_OBJECT_FIELD";
    MapperKind["ARGUMENT"] = "MapperKind.ARGUMENT";
    MapperKind["ENUM_VALUE"] = "MapperKind.ENUM_VALUE";
})(exports.MapperKind || (exports.MapperKind = {}));

function createNamedStub(name, type) {
    var constructor;
    if (type === 'object') {
        constructor = graphql.GraphQLObjectType;
    }
    else if (type === 'interface') {
        constructor = graphql.GraphQLInterfaceType;
    }
    else {
        constructor = graphql.GraphQLInputObjectType;
    }
    return new constructor({
        name: name,
        fields: {
            __fake: {
                type: graphql.GraphQLString,
            },
        },
    });
}
function createStub(node, type) {
    switch (node.kind) {
        case graphql.Kind.LIST_TYPE:
            return new graphql.GraphQLList(createStub(node.type, type));
        case graphql.Kind.NON_NULL_TYPE:
            return new graphql.GraphQLNonNull(createStub(node.type, type));
        default:
            if (type === 'output') {
                return createNamedStub(node.name.value, 'object');
            }
            return createNamedStub(node.name.value, 'input');
    }
}
function isNamedStub(type) {
    if (graphql.isObjectType(type) || graphql.isInterfaceType(type) || graphql.isInputObjectType(type)) {
        var fields = type.getFields();
        var fieldNames = Object.keys(fields);
        return fieldNames.length === 1 && fields[fieldNames[0]].name === '__fake';
    }
    return false;
}
function getBuiltInForStub(type) {
    switch (type.name) {
        case graphql.GraphQLInt.name:
            return graphql.GraphQLInt;
        case graphql.GraphQLFloat.name:
            return graphql.GraphQLFloat;
        case graphql.GraphQLString.name:
            return graphql.GraphQLString;
        case graphql.GraphQLBoolean.name:
            return graphql.GraphQLBoolean;
        case graphql.GraphQLID.name:
            return graphql.GraphQLID;
        default:
            return type;
    }
}

function rewireTypes(originalTypeMap, directives, options) {
    if (options === void 0) { options = {
        skipPruning: false,
    }; }
    var referenceTypeMap = Object.create(null);
    Object.keys(originalTypeMap).forEach(function (typeName) {
        referenceTypeMap[typeName] = originalTypeMap[typeName];
    });
    var newTypeMap = Object.create(null);
    Object.keys(referenceTypeMap).forEach(function (typeName) {
        var namedType = referenceTypeMap[typeName];
        if (namedType == null || typeName.startsWith('__')) {
            return;
        }
        var newName = namedType.name;
        if (newName.startsWith('__')) {
            return;
        }
        if (newTypeMap[newName] != null) {
            throw new Error("Duplicate schema type name " + newName);
        }
        newTypeMap[newName] = namedType;
    });
    Object.keys(newTypeMap).forEach(function (typeName) {
        newTypeMap[typeName] = rewireNamedType(newTypeMap[typeName]);
    });
    var newDirectives = directives.map(function (directive) { return rewireDirective(directive); });
    // TODO:
    // consider removing the default level of pruning in v7,
    // see comments below on the pruneTypes function.
    return options.skipPruning
        ? {
            typeMap: newTypeMap,
            directives: newDirectives,
        }
        : pruneTypes(newTypeMap, newDirectives);
    function rewireDirective(directive) {
        if (graphql.isSpecifiedDirective(directive)) {
            return directive;
        }
        var directiveConfig = directive.toConfig();
        directiveConfig.args = rewireArgs(directiveConfig.args);
        return new graphql.GraphQLDirective(directiveConfig);
    }
    function rewireArgs(args) {
        var rewiredArgs = {};
        Object.keys(args).forEach(function (argName) {
            var arg = args[argName];
            var rewiredArgType = rewireType(arg.type);
            if (rewiredArgType != null) {
                arg.type = rewiredArgType;
                rewiredArgs[argName] = arg;
            }
        });
        return rewiredArgs;
    }
    function rewireNamedType(type) {
        if (graphql.isObjectType(type)) {
            var config_1 = type.toConfig();
            var newConfig = tslib.__assign(tslib.__assign({}, config_1), { fields: function () { return rewireFields(config_1.fields); }, interfaces: function () { return rewireNamedTypes(config_1.interfaces); } });
            return new graphql.GraphQLObjectType(newConfig);
        }
        else if (graphql.isInterfaceType(type)) {
            var config_2 = type.toConfig();
            var newConfig = tslib.__assign(tslib.__assign({}, config_2), { fields: function () { return rewireFields(config_2.fields); } });
            if ('interfaces' in newConfig) {
                newConfig.interfaces = function () {
                    return rewireNamedTypes(config_2.interfaces);
                };
            }
            return new graphql.GraphQLInterfaceType(newConfig);
        }
        else if (graphql.isUnionType(type)) {
            var config_3 = type.toConfig();
            var newConfig = tslib.__assign(tslib.__assign({}, config_3), { types: function () { return rewireNamedTypes(config_3.types); } });
            return new graphql.GraphQLUnionType(newConfig);
        }
        else if (graphql.isInputObjectType(type)) {
            var config_4 = type.toConfig();
            var newConfig = tslib.__assign(tslib.__assign({}, config_4), { fields: function () { return rewireInputFields(config_4.fields); } });
            return new graphql.GraphQLInputObjectType(newConfig);
        }
        else if (graphql.isEnumType(type)) {
            var enumConfig = type.toConfig();
            return new graphql.GraphQLEnumType(enumConfig);
        }
        else if (graphql.isScalarType(type)) {
            if (graphql.isSpecifiedScalarType(type)) {
                return type;
            }
            var scalarConfig = type.toConfig();
            return new graphql.GraphQLScalarType(scalarConfig);
        }
        throw new Error("Unexpected schema type: " + type);
    }
    function rewireFields(fields) {
        var rewiredFields = {};
        Object.keys(fields).forEach(function (fieldName) {
            var field = fields[fieldName];
            var rewiredFieldType = rewireType(field.type);
            if (rewiredFieldType != null) {
                field.type = rewiredFieldType;
                field.args = rewireArgs(field.args);
                rewiredFields[fieldName] = field;
            }
        });
        return rewiredFields;
    }
    function rewireInputFields(fields) {
        var rewiredFields = {};
        Object.keys(fields).forEach(function (fieldName) {
            var field = fields[fieldName];
            var rewiredFieldType = rewireType(field.type);
            if (rewiredFieldType != null) {
                field.type = rewiredFieldType;
                rewiredFields[fieldName] = field;
            }
        });
        return rewiredFields;
    }
    function rewireNamedTypes(namedTypes) {
        var rewiredTypes = [];
        namedTypes.forEach(function (namedType) {
            var rewiredType = rewireType(namedType);
            if (rewiredType != null) {
                rewiredTypes.push(rewiredType);
            }
        });
        return rewiredTypes;
    }
    function rewireType(type) {
        if (graphql.isListType(type)) {
            var rewiredType = rewireType(type.ofType);
            return rewiredType != null ? new graphql.GraphQLList(rewiredType) : null;
        }
        else if (graphql.isNonNullType(type)) {
            var rewiredType = rewireType(type.ofType);
            return rewiredType != null ? new graphql.GraphQLNonNull(rewiredType) : null;
        }
        else if (graphql.isNamedType(type)) {
            var rewiredType = referenceTypeMap[type.name];
            if (rewiredType === undefined) {
                rewiredType = isNamedStub(type) ? getBuiltInForStub(type) : rewireNamedType(type);
                newTypeMap[rewiredType.name] = referenceTypeMap[type.name] = rewiredType;
            }
            return rewiredType != null ? newTypeMap[rewiredType.name] : null;
        }
        return null;
    }
}
// TODO:
// consider removing the default level of pruning in v7
//
// Pruning during mapSchema limits the ability to create an unpruned schema, which may be of use
// to some library users. pruning is now recommended via the dedicated pruneSchema function
// which does not force pruning on library users and gives granular control in terms of pruning
// types.
function pruneTypes(typeMap, directives) {
    var newTypeMap = {};
    var implementedInterfaces = {};
    Object.keys(typeMap).forEach(function (typeName) {
        var namedType = typeMap[typeName];
        if ('getInterfaces' in namedType) {
            namedType.getInterfaces().forEach(function (iface) {
                implementedInterfaces[iface.name] = true;
            });
        }
    });
    var prunedTypeMap = false;
    var typeNames = Object.keys(typeMap);
    for (var i = 0; i < typeNames.length; i++) {
        var typeName = typeNames[i];
        var type = typeMap[typeName];
        if (graphql.isObjectType(type) || graphql.isInputObjectType(type)) {
            // prune types with no fields
            if (Object.keys(type.getFields()).length) {
                newTypeMap[typeName] = type;
            }
            else {
                prunedTypeMap = true;
            }
        }
        else if (graphql.isUnionType(type)) {
            // prune unions without underlying types
            if (type.getTypes().length) {
                newTypeMap[typeName] = type;
            }
            else {
                prunedTypeMap = true;
            }
        }
        else if (graphql.isInterfaceType(type)) {
            // prune interfaces without fields or without implementations
            if (Object.keys(type.getFields()).length && implementedInterfaces[type.name]) {
                newTypeMap[typeName] = type;
            }
            else {
                prunedTypeMap = true;
            }
        }
        else {
            newTypeMap[typeName] = type;
        }
    }
    // every prune requires another round of healing
    return prunedTypeMap ? rewireTypes(newTypeMap, directives) : { typeMap: typeMap, directives: directives };
}

function transformInputValue(type, value, transformer) {
    if (value == null) {
        return value;
    }
    var nullableType = graphql.getNullableType(type);
    if (graphql.isLeafType(nullableType)) {
        return transformer(nullableType, value);
    }
    else if (graphql.isListType(nullableType)) {
        return value.map(function (listMember) { return transformInputValue(nullableType.ofType, listMember, transformer); });
    }
    else if (graphql.isInputObjectType(nullableType)) {
        var fields_1 = nullableType.getFields();
        var newValue_1 = {};
        Object.keys(value).forEach(function (key) {
            newValue_1[key] = transformInputValue(fields_1[key].type, value[key], transformer);
        });
        return newValue_1;
    }
    // unreachable, no other possible return value
}
function serializeInputValue(type, value) {
    return transformInputValue(type, value, function (t, v) { return t.serialize(v); });
}
function parseInputValue(type, value) {
    return transformInputValue(type, value, function (t, v) { return t.parseValue(v); });
}
function parseInputValueLiteral(type, value) {
    return transformInputValue(type, value, function (t, v) { return t.parseLiteral(v, {}); });
}

function mapSchema(schema, schemaMapper) {
    if (schemaMapper === void 0) { schemaMapper = {}; }
    var originalTypeMap = schema.getTypeMap();
    var newTypeMap = mapDefaultValues(originalTypeMap, schema, serializeInputValue);
    newTypeMap = mapTypes(newTypeMap, schema, schemaMapper, function (type) { return graphql.isLeafType(type); });
    newTypeMap = mapEnumValues(newTypeMap, schema, schemaMapper);
    newTypeMap = mapDefaultValues(newTypeMap, schema, parseInputValue);
    newTypeMap = mapTypes(newTypeMap, schema, schemaMapper, function (type) { return !graphql.isLeafType(type); });
    newTypeMap = mapFields(newTypeMap, schema, schemaMapper);
    newTypeMap = mapArguments(newTypeMap, schema, schemaMapper);
    var originalDirectives = schema.getDirectives();
    var newDirectives = mapDirectives(originalDirectives, schema, schemaMapper);
    var queryType = schema.getQueryType();
    var mutationType = schema.getMutationType();
    var subscriptionType = schema.getSubscriptionType();
    var newQueryTypeName = queryType != null ? (newTypeMap[queryType.name] != null ? newTypeMap[queryType.name].name : undefined) : undefined;
    var newMutationTypeName = mutationType != null
        ? newTypeMap[mutationType.name] != null
            ? newTypeMap[mutationType.name].name
            : undefined
        : undefined;
    var newSubscriptionTypeName = subscriptionType != null
        ? newTypeMap[subscriptionType.name] != null
            ? newTypeMap[subscriptionType.name].name
            : undefined
        : undefined;
    var _a = rewireTypes(newTypeMap, newDirectives), typeMap = _a.typeMap, directives = _a.directives;
    return new graphql.GraphQLSchema(tslib.__assign(tslib.__assign({}, schema.toConfig()), { query: newQueryTypeName ? typeMap[newQueryTypeName] : undefined, mutation: newMutationTypeName ? typeMap[newMutationTypeName] : undefined, subscription: newSubscriptionTypeName != null ? typeMap[newSubscriptionTypeName] : undefined, types: Object.keys(typeMap).map(function (typeName) { return typeMap[typeName]; }), directives: directives }));
}
function mapTypes(originalTypeMap, schema, schemaMapper, testFn) {
    if (testFn === void 0) { testFn = function () { return true; }; }
    var newTypeMap = {};
    Object.keys(originalTypeMap).forEach(function (typeName) {
        if (!typeName.startsWith('__')) {
            var originalType = originalTypeMap[typeName];
            if (originalType == null || !testFn(originalType)) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var typeMapper = getTypeMapper(schema, schemaMapper, typeName);
            if (typeMapper == null) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var maybeNewType = typeMapper(originalType, schema);
            if (maybeNewType === undefined) {
                newTypeMap[typeName] = originalType;
                return;
            }
            newTypeMap[typeName] = maybeNewType;
        }
    });
    return newTypeMap;
}
function mapEnumValues(originalTypeMap, schema, schemaMapper) {
    var _a;
    var enumValueMapper = getEnumValueMapper(schemaMapper);
    if (!enumValueMapper) {
        return originalTypeMap;
    }
    return mapTypes(originalTypeMap, schema, (_a = {},
        _a[exports.MapperKind.ENUM_TYPE] = function (type) {
            var config = type.toConfig();
            var originalEnumValueConfigMap = config.values;
            var newEnumValueConfigMap = {};
            Object.keys(originalEnumValueConfigMap).forEach(function (externalValue) {
                var originalEnumValueConfig = originalEnumValueConfigMap[externalValue];
                var mappedEnumValue = enumValueMapper(originalEnumValueConfig, type.name, schema, externalValue);
                if (mappedEnumValue === undefined) {
                    newEnumValueConfigMap[externalValue] = originalEnumValueConfig;
                }
                else if (Array.isArray(mappedEnumValue)) {
                    var _a = tslib.__read(mappedEnumValue, 2), newExternalValue = _a[0], newEnumValueConfig = _a[1];
                    newEnumValueConfigMap[newExternalValue] =
                        newEnumValueConfig === undefined ? originalEnumValueConfig : newEnumValueConfig;
                }
                else if (mappedEnumValue !== null) {
                    newEnumValueConfigMap[externalValue] = mappedEnumValue;
                }
            });
            return correctASTNodes(new graphql.GraphQLEnumType(tslib.__assign(tslib.__assign({}, config), { values: newEnumValueConfigMap })));
        },
        _a), function (type) { return graphql.isEnumType(type); });
}
function mapDefaultValues(originalTypeMap, schema, fn) {
    var _a, _b;
    var newTypeMap = mapArguments(originalTypeMap, schema, (_a = {},
        _a[exports.MapperKind.ARGUMENT] = function (argumentConfig) {
            if (argumentConfig.defaultValue === undefined) {
                return argumentConfig;
            }
            var maybeNewType = getNewType(originalTypeMap, argumentConfig.type);
            if (maybeNewType != null) {
                return tslib.__assign(tslib.__assign({}, argumentConfig), { defaultValue: fn(maybeNewType, argumentConfig.defaultValue) });
            }
        },
        _a));
    return mapFields(newTypeMap, schema, (_b = {},
        _b[exports.MapperKind.INPUT_OBJECT_FIELD] = function (inputFieldConfig) {
            if (inputFieldConfig.defaultValue === undefined) {
                return inputFieldConfig;
            }
            var maybeNewType = getNewType(newTypeMap, inputFieldConfig.type);
            if (maybeNewType != null) {
                return tslib.__assign(tslib.__assign({}, inputFieldConfig), { defaultValue: fn(maybeNewType, inputFieldConfig.defaultValue) });
            }
        },
        _b));
}
function getNewType(newTypeMap, type) {
    if (graphql.isListType(type)) {
        var newType = getNewType(newTypeMap, type.ofType);
        return newType != null ? new graphql.GraphQLList(newType) : null;
    }
    else if (graphql.isNonNullType(type)) {
        var newType = getNewType(newTypeMap, type.ofType);
        return newType != null ? new graphql.GraphQLNonNull(newType) : null;
    }
    else if (graphql.isNamedType(type)) {
        var newType = newTypeMap[type.name];
        return newType != null ? newType : null;
    }
    return null;
}
function mapFields(originalTypeMap, schema, schemaMapper) {
    var newTypeMap = {};
    Object.keys(originalTypeMap).forEach(function (typeName) {
        if (!typeName.startsWith('__')) {
            var originalType = originalTypeMap[typeName];
            if (!graphql.isObjectType(originalType) && !graphql.isInterfaceType(originalType) && !graphql.isInputObjectType(originalType)) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var fieldMapper_1 = getFieldMapper(schema, schemaMapper, typeName);
            if (fieldMapper_1 == null) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var config = originalType.toConfig();
            var originalFieldConfigMap_1 = config.fields;
            var newFieldConfigMap_1 = {};
            Object.keys(originalFieldConfigMap_1).forEach(function (fieldName) {
                var originalFieldConfig = originalFieldConfigMap_1[fieldName];
                var mappedField = fieldMapper_1(originalFieldConfig, fieldName, typeName, schema);
                if (mappedField === undefined) {
                    newFieldConfigMap_1[fieldName] = originalFieldConfig;
                }
                else if (Array.isArray(mappedField)) {
                    var _a = tslib.__read(mappedField, 2), newFieldName = _a[0], newFieldConfig = _a[1];
                    if (newFieldConfig.astNode != null) {
                        newFieldConfig.astNode = tslib.__assign(tslib.__assign({}, newFieldConfig.astNode), { name: tslib.__assign(tslib.__assign({}, newFieldConfig.astNode.name), { value: newFieldName }) });
                    }
                    newFieldConfigMap_1[newFieldName] = newFieldConfig === undefined ? originalFieldConfig : newFieldConfig;
                }
                else if (mappedField !== null) {
                    newFieldConfigMap_1[fieldName] = mappedField;
                }
            });
            if (graphql.isObjectType(originalType)) {
                newTypeMap[typeName] = correctASTNodes(new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_1 })));
            }
            else if (graphql.isInterfaceType(originalType)) {
                newTypeMap[typeName] = correctASTNodes(new graphql.GraphQLInterfaceType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_1 })));
            }
            else {
                newTypeMap[typeName] = correctASTNodes(new graphql.GraphQLInputObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_1 })));
            }
        }
    });
    return newTypeMap;
}
function mapArguments(originalTypeMap, schema, schemaMapper) {
    var newTypeMap = {};
    Object.keys(originalTypeMap).forEach(function (typeName) {
        if (!typeName.startsWith('__')) {
            var originalType = originalTypeMap[typeName];
            if (!graphql.isObjectType(originalType) && !graphql.isInterfaceType(originalType)) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var argumentMapper_1 = getArgumentMapper(schemaMapper);
            if (argumentMapper_1 == null) {
                newTypeMap[typeName] = originalType;
                return;
            }
            var config = originalType.toConfig();
            var originalFieldConfigMap_2 = config.fields;
            var newFieldConfigMap_2 = {};
            Object.keys(originalFieldConfigMap_2).forEach(function (fieldName) {
                var originalFieldConfig = originalFieldConfigMap_2[fieldName];
                var originalArgumentConfigMap = originalFieldConfig.args;
                if (originalArgumentConfigMap == null) {
                    newFieldConfigMap_2[fieldName] = originalFieldConfig;
                    return;
                }
                var argumentNames = Object.keys(originalArgumentConfigMap);
                if (!argumentNames.length) {
                    newFieldConfigMap_2[fieldName] = originalFieldConfig;
                    return;
                }
                var newArgumentConfigMap = {};
                argumentNames.forEach(function (argumentName) {
                    var originalArgumentConfig = originalArgumentConfigMap[argumentName];
                    var mappedArgument = argumentMapper_1(originalArgumentConfig, fieldName, typeName, schema);
                    if (mappedArgument === undefined) {
                        newArgumentConfigMap[argumentName] = originalArgumentConfig;
                    }
                    else if (Array.isArray(mappedArgument)) {
                        var _a = tslib.__read(mappedArgument, 2), newArgumentName = _a[0], newArgumentConfig = _a[1];
                        newArgumentConfigMap[newArgumentName] = newArgumentConfig;
                    }
                    else if (mappedArgument !== null) {
                        newArgumentConfigMap[argumentName] = mappedArgument;
                    }
                });
                newFieldConfigMap_2[fieldName] = tslib.__assign(tslib.__assign({}, originalFieldConfig), { args: newArgumentConfigMap });
            });
            if (graphql.isObjectType(originalType)) {
                newTypeMap[typeName] = new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_2 }));
            }
            else if (graphql.isInterfaceType(originalType)) {
                newTypeMap[typeName] = new graphql.GraphQLInterfaceType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_2 }));
            }
            else {
                newTypeMap[typeName] = new graphql.GraphQLInputObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_2 }));
            }
        }
    });
    return newTypeMap;
}
function mapDirectives(originalDirectives, schema, schemaMapper) {
    var directiveMapper = getDirectiveMapper(schemaMapper);
    if (directiveMapper == null) {
        return originalDirectives.slice();
    }
    var newDirectives = [];
    originalDirectives.forEach(function (directive) {
        var mappedDirective = directiveMapper(directive, schema);
        if (mappedDirective === undefined) {
            newDirectives.push(directive);
        }
        else if (mappedDirective !== null) {
            newDirectives.push(mappedDirective);
        }
    });
    return newDirectives;
}
function getTypeSpecifiers(schema, typeName) {
    var type = schema.getType(typeName);
    var specifiers = [exports.MapperKind.TYPE];
    if (graphql.isObjectType(type)) {
        specifiers.push(exports.MapperKind.COMPOSITE_TYPE, exports.MapperKind.OBJECT_TYPE);
        var query = schema.getQueryType();
        var mutation = schema.getMutationType();
        var subscription = schema.getSubscriptionType();
        if (query != null && typeName === query.name) {
            specifiers.push(exports.MapperKind.ROOT_OBJECT, exports.MapperKind.QUERY);
        }
        else if (mutation != null && typeName === mutation.name) {
            specifiers.push(exports.MapperKind.ROOT_OBJECT, exports.MapperKind.MUTATION);
        }
        else if (subscription != null && typeName === subscription.name) {
            specifiers.push(exports.MapperKind.ROOT_OBJECT, exports.MapperKind.SUBSCRIPTION);
        }
    }
    else if (graphql.isInputObjectType(type)) {
        specifiers.push(exports.MapperKind.INPUT_OBJECT_TYPE);
    }
    else if (graphql.isInterfaceType(type)) {
        specifiers.push(exports.MapperKind.COMPOSITE_TYPE, exports.MapperKind.ABSTRACT_TYPE, exports.MapperKind.INTERFACE_TYPE);
    }
    else if (graphql.isUnionType(type)) {
        specifiers.push(exports.MapperKind.COMPOSITE_TYPE, exports.MapperKind.ABSTRACT_TYPE, exports.MapperKind.UNION_TYPE);
    }
    else if (graphql.isEnumType(type)) {
        specifiers.push(exports.MapperKind.ENUM_TYPE);
    }
    else if (graphql.isScalarType(type)) {
        specifiers.push(exports.MapperKind.SCALAR_TYPE);
    }
    return specifiers;
}
function getTypeMapper(schema, schemaMapper, typeName) {
    var specifiers = getTypeSpecifiers(schema, typeName);
    var typeMapper;
    var stack = tslib.__spread(specifiers);
    while (!typeMapper && stack.length > 0) {
        var next = stack.pop();
        typeMapper = schemaMapper[next];
    }
    return typeMapper != null ? typeMapper : null;
}
function getFieldSpecifiers(schema, typeName) {
    var type = schema.getType(typeName);
    var specifiers = [exports.MapperKind.FIELD];
    if (graphql.isObjectType(type)) {
        specifiers.push(exports.MapperKind.COMPOSITE_FIELD, exports.MapperKind.OBJECT_FIELD);
        var query = schema.getQueryType();
        var mutation = schema.getMutationType();
        var subscription = schema.getSubscriptionType();
        if (query != null && typeName === query.name) {
            specifiers.push(exports.MapperKind.ROOT_FIELD, exports.MapperKind.QUERY_ROOT_FIELD);
        }
        else if (mutation != null && typeName === mutation.name) {
            specifiers.push(exports.MapperKind.ROOT_FIELD, exports.MapperKind.MUTATION_ROOT_FIELD);
        }
        else if (subscription != null && typeName === subscription.name) {
            specifiers.push(exports.MapperKind.ROOT_FIELD, exports.MapperKind.SUBSCRIPTION_ROOT_FIELD);
        }
    }
    else if (graphql.isInterfaceType(type)) {
        specifiers.push(exports.MapperKind.COMPOSITE_FIELD, exports.MapperKind.INTERFACE_FIELD);
    }
    else if (graphql.isInputObjectType(type)) {
        specifiers.push(exports.MapperKind.INPUT_OBJECT_FIELD);
    }
    return specifiers;
}
function getFieldMapper(schema, schemaMapper, typeName) {
    var specifiers = getFieldSpecifiers(schema, typeName);
    var fieldMapper;
    var stack = tslib.__spread(specifiers);
    while (!fieldMapper && stack.length > 0) {
        var next = stack.pop();
        fieldMapper = schemaMapper[next];
    }
    return fieldMapper != null ? fieldMapper : null;
}
function getArgumentMapper(schemaMapper) {
    var argumentMapper = schemaMapper[exports.MapperKind.ARGUMENT];
    return argumentMapper != null ? argumentMapper : null;
}
function getDirectiveMapper(schemaMapper) {
    var directiveMapper = schemaMapper[exports.MapperKind.DIRECTIVE];
    return directiveMapper != null ? directiveMapper : null;
}
function getEnumValueMapper(schemaMapper) {
    var enumValueMapper = schemaMapper[exports.MapperKind.ENUM_VALUE];
    return enumValueMapper != null ? enumValueMapper : null;
}
function correctASTNodes(type) {
    if (graphql.isObjectType(type)) {
        var config = type.toConfig();
        if (config.astNode != null) {
            var fields_1 = [];
            Object.values(config.fields).forEach(function (fieldConfig) {
                if (fieldConfig.astNode != null) {
                    fields_1.push(fieldConfig.astNode);
                }
            });
            config.astNode = tslib.__assign(tslib.__assign({}, config.astNode), { kind: graphql.Kind.OBJECT_TYPE_DEFINITION, fields: fields_1 });
        }
        if (config.extensionASTNodes != null) {
            config.extensionASTNodes = config.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { kind: graphql.Kind.OBJECT_TYPE_EXTENSION, fields: undefined })); });
        }
        return new graphql.GraphQLObjectType(config);
    }
    else if (graphql.isInterfaceType(type)) {
        var config = type.toConfig();
        if (config.astNode != null) {
            var fields_2 = [];
            Object.values(config.fields).forEach(function (fieldConfig) {
                if (fieldConfig.astNode != null) {
                    fields_2.push(fieldConfig.astNode);
                }
            });
            config.astNode = tslib.__assign(tslib.__assign({}, config.astNode), { kind: graphql.Kind.INTERFACE_TYPE_DEFINITION, fields: fields_2 });
        }
        if (config.extensionASTNodes != null) {
            config.extensionASTNodes = config.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { kind: graphql.Kind.INTERFACE_TYPE_EXTENSION, fields: undefined })); });
        }
        return new graphql.GraphQLInterfaceType(config);
    }
    else if (graphql.isInputObjectType(type)) {
        var config = type.toConfig();
        if (config.astNode != null) {
            var fields_3 = [];
            Object.values(config.fields).forEach(function (fieldConfig) {
                if (fieldConfig.astNode != null) {
                    fields_3.push(fieldConfig.astNode);
                }
            });
            config.astNode = tslib.__assign(tslib.__assign({}, config.astNode), { kind: graphql.Kind.INPUT_OBJECT_TYPE_DEFINITION, fields: fields_3 });
        }
        if (config.extensionASTNodes != null) {
            config.extensionASTNodes = config.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { kind: graphql.Kind.INPUT_OBJECT_TYPE_EXTENSION, fields: undefined })); });
        }
        return new graphql.GraphQLInputObjectType(config);
    }
    else if (graphql.isEnumType(type)) {
        var config = type.toConfig();
        if (config.astNode != null) {
            var values_1 = [];
            Object.values(config.values).forEach(function (enumValueConfig) {
                if (enumValueConfig.astNode != null) {
                    values_1.push(enumValueConfig.astNode);
                }
            });
            config.astNode = tslib.__assign(tslib.__assign({}, config.astNode), { values: values_1 });
        }
        if (config.extensionASTNodes != null) {
            config.extensionASTNodes = config.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { values: undefined })); });
        }
        return new graphql.GraphQLEnumType(config);
    }
    else {
        return type;
    }
}

function filterSchema(_a) {
    var _b;
    var schema = _a.schema, _c = _a.rootFieldFilter, rootFieldFilter = _c === void 0 ? function () { return true; } : _c, _d = _a.typeFilter, typeFilter = _d === void 0 ? function () { return true; } : _d, _e = _a.fieldFilter, fieldFilter = _e === void 0 ? function () { return true; } : _e, _f = _a.objectFieldFilter, objectFieldFilter = _f === void 0 ? function () { return true; } : _f, _g = _a.interfaceFieldFilter, interfaceFieldFilter = _g === void 0 ? function () { return true; } : _g;
    var filteredSchema = mapSchema(schema, (_b = {},
        _b[exports.MapperKind.QUERY] = function (type) { return filterRootFields(type, 'Query', rootFieldFilter); },
        _b[exports.MapperKind.MUTATION] = function (type) { return filterRootFields(type, 'Mutation', rootFieldFilter); },
        _b[exports.MapperKind.SUBSCRIPTION] = function (type) { return filterRootFields(type, 'Subscription', rootFieldFilter); },
        _b[exports.MapperKind.OBJECT_TYPE] = function (type) {
            return typeFilter(type.name, type)
                ? filterElementFields(type, objectFieldFilter || fieldFilter, graphql.GraphQLObjectType)
                : null;
        },
        _b[exports.MapperKind.INTERFACE_TYPE] = function (type) {
            return typeFilter(type.name, type)
                ? filterElementFields(type, interfaceFieldFilter, graphql.GraphQLInterfaceType)
                : null;
        },
        _b[exports.MapperKind.UNION_TYPE] = function (type) { return (typeFilter(type.name, type) ? undefined : null); },
        _b[exports.MapperKind.INPUT_OBJECT_TYPE] = function (type) { return (typeFilter(type.name, type) ? undefined : null); },
        _b[exports.MapperKind.ENUM_TYPE] = function (type) { return (typeFilter(type.name, type) ? undefined : null); },
        _b[exports.MapperKind.SCALAR_TYPE] = function (type) { return (typeFilter(type.name, type) ? undefined : null); },
        _b));
    return filteredSchema;
}
function filterRootFields(type, operation, rootFieldFilter) {
    var config = type.toConfig();
    Object.keys(config.fields).forEach(function (fieldName) {
        if (!rootFieldFilter(operation, fieldName, config.fields[fieldName])) {
            delete config.fields[fieldName];
        }
    });
    return new graphql.GraphQLObjectType(config);
}
function filterElementFields(type, fieldFilter, ElementConstructor) {
    var config = type.toConfig();
    Object.keys(config.fields).forEach(function (fieldName) {
        if (!fieldFilter(type.name, fieldName, config.fields[fieldName])) {
            delete config.fields[fieldName];
        }
    });
    return new ElementConstructor(config);
}

function cloneDirective(directive) {
    return graphql.isSpecifiedDirective(directive) ? directive : new graphql.GraphQLDirective(directive.toConfig());
}
function cloneType(type) {
    if (graphql.isObjectType(type)) {
        var config = type.toConfig();
        return new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { interfaces: typeof config.interfaces === 'function' ? config.interfaces : config.interfaces.slice() }));
    }
    else if (graphql.isInterfaceType(type)) {
        var config = type.toConfig();
        var newConfig = tslib.__assign(tslib.__assign({}, config), { interfaces: tslib.__spread(((typeof config.interfaces === 'function' ? config.interfaces() : config.interfaces) || [])) });
        return new graphql.GraphQLInterfaceType(newConfig);
    }
    else if (graphql.isUnionType(type)) {
        var config = type.toConfig();
        return new graphql.GraphQLUnionType(tslib.__assign(tslib.__assign({}, config), { types: config.types.slice() }));
    }
    else if (graphql.isInputObjectType(type)) {
        return new graphql.GraphQLInputObjectType(type.toConfig());
    }
    else if (graphql.isEnumType(type)) {
        return new graphql.GraphQLEnumType(type.toConfig());
    }
    else if (graphql.isScalarType(type)) {
        return graphql.isSpecifiedScalarType(type) ? type : new graphql.GraphQLScalarType(type.toConfig());
    }
    throw new Error("Invalid type " + type);
}
function cloneSchema(schema) {
    return mapSchema(schema);
}

// Update any references to named schema types that disagree with the named
// types found in schema.getTypeMap().
//
// healSchema and its callers (visitSchema/visitSchemaDirectives) all modify the schema in place.
// Therefore, private variables (such as the stored implementation map and the proper root types)
// are not updated.
//
// If this causes issues, the schema could be more aggressively healed as follows:
//
// healSchema(schema);
// const config = schema.toConfig()
// const healedSchema = new GraphQLSchema({
//   ...config,
//   query: schema.getType('<desired new root query type name>'),
//   mutation: schema.getType('<desired new root mutation type name>'),
//   subscription: schema.getType('<desired new root subscription type name>'),
// });
//
// One can then also -- if necessary --  assign the correct private variables to the initial schema
// as follows:
// Object.assign(schema, healedSchema);
//
// These steps are not taken automatically to preserve backwards compatibility with graphql-tools v4.
// See https://github.com/ardatan/graphql-tools/issues/1462
//
// They were briefly taken in v5, but can now be phased out as they were only required when other
// areas of the codebase were using healSchema and visitSchema more extensively.
//
function healSchema(schema) {
    healTypes(schema.getTypeMap(), schema.getDirectives());
    return schema;
}
function healTypes(originalTypeMap, directives, config) {
    var e_1, _a;
    if (config === void 0) { config = {
        skipPruning: false,
    }; }
    var actualNamedTypeMap = Object.create(null);
    // If any of the .name properties of the GraphQLNamedType objects in
    // schema.getTypeMap() have changed, the keys of the type map need to
    // be updated accordingly.
    Object.entries(originalTypeMap).forEach(function (_a) {
        var _b = tslib.__read(_a, 2), typeName = _b[0], namedType = _b[1];
        if (namedType == null || typeName.startsWith('__')) {
            return;
        }
        var actualName = namedType.name;
        if (actualName.startsWith('__')) {
            return;
        }
        if (actualName in actualNamedTypeMap) {
            throw new Error("Duplicate schema type name " + actualName);
        }
        actualNamedTypeMap[actualName] = namedType;
        // Note: we are deliberately leaving namedType in the schema by its
        // original name (which might be different from actualName), so that
        // references by that name can be healed.
    });
    // Now add back every named type by its actual name.
    Object.entries(actualNamedTypeMap).forEach(function (_a) {
        var _b = tslib.__read(_a, 2), typeName = _b[0], namedType = _b[1];
        originalTypeMap[typeName] = namedType;
    });
    // Directive declaration argument types can refer to named types.
    directives.forEach(function (decl) {
        decl.args = decl.args.filter(function (arg) {
            arg.type = healType(arg.type);
            return arg.type !== null;
        });
    });
    Object.entries(originalTypeMap).forEach(function (_a) {
        var _b = tslib.__read(_a, 2), typeName = _b[0], namedType = _b[1];
        // Heal all named types, except for dangling references, kept only to redirect.
        if (!typeName.startsWith('__') && typeName in actualNamedTypeMap) {
            if (namedType != null) {
                healNamedType(namedType);
            }
        }
    });
    try {
        for (var _b = tslib.__values(Object.keys(originalTypeMap)), _c = _b.next(); !_c.done; _c = _b.next()) {
            var typeName = _c.value;
            if (!typeName.startsWith('__') && !(typeName in actualNamedTypeMap)) {
                delete originalTypeMap[typeName];
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
    if (!config.skipPruning) {
        // TODO:
        // consider removing the default level of pruning in v7,
        // see comments below on the pruneTypes function.
        pruneTypes$1(originalTypeMap, directives);
    }
    function healNamedType(type) {
        if (graphql.isObjectType(type)) {
            healFields(type);
            healInterfaces(type);
            return;
        }
        else if (graphql.isInterfaceType(type)) {
            healFields(type);
            if ('getInterfaces' in type) {
                healInterfaces(type);
            }
            return;
        }
        else if (graphql.isUnionType(type)) {
            healUnderlyingTypes(type);
            return;
        }
        else if (graphql.isInputObjectType(type)) {
            healInputFields(type);
            return;
        }
        else if (graphql.isLeafType(type)) {
            return;
        }
        throw new Error("Unexpected schema type: " + type);
    }
    function healFields(type) {
        var e_2, _a;
        var fieldMap = type.getFields();
        try {
            for (var _b = tslib.__values(Object.entries(fieldMap)), _c = _b.next(); !_c.done; _c = _b.next()) {
                var _d = tslib.__read(_c.value, 2), key = _d[0], field = _d[1];
                field.args
                    .map(function (arg) {
                    arg.type = healType(arg.type);
                    return arg.type === null ? null : arg;
                })
                    .filter(Boolean);
                field.type = healType(field.type);
                if (field.type === null) {
                    delete fieldMap[key];
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
    }
    function healInterfaces(type) {
        if ('getInterfaces' in type) {
            var interfaces = type.getInterfaces();
            interfaces.push.apply(interfaces, tslib.__spread(interfaces
                .splice(0)
                .map(function (iface) { return healType(iface); })
                .filter(Boolean)));
        }
    }
    function healInputFields(type) {
        var e_3, _a;
        var fieldMap = type.getFields();
        try {
            for (var _b = tslib.__values(Object.entries(fieldMap)), _c = _b.next(); !_c.done; _c = _b.next()) {
                var _d = tslib.__read(_c.value, 2), key = _d[0], field = _d[1];
                field.type = healType(field.type);
                if (field.type === null) {
                    delete fieldMap[key];
                }
            }
        }
        catch (e_3_1) { e_3 = { error: e_3_1 }; }
        finally {
            try {
                if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
            }
            finally { if (e_3) throw e_3.error; }
        }
    }
    function healUnderlyingTypes(type) {
        var types = type.getTypes();
        types.push.apply(types, tslib.__spread(types
            .splice(0)
            .map(function (t) { return healType(t); })
            .filter(Boolean)));
    }
    function healType(type) {
        // Unwrap the two known wrapper types
        if (graphql.isListType(type)) {
            var healedType = healType(type.ofType);
            return healedType != null ? new graphql.GraphQLList(healedType) : null;
        }
        else if (graphql.isNonNullType(type)) {
            var healedType = healType(type.ofType);
            return healedType != null ? new graphql.GraphQLNonNull(healedType) : null;
        }
        else if (graphql.isNamedType(type)) {
            // If a type annotation on a field or an argument or a union member is
            // any `GraphQLNamedType` with a `name`, then it must end up identical
            // to `schema.getType(name)`, since `schema.getTypeMap()` is the source
            // of truth for all named schema types.
            // Note that new types can still be simply added by adding a field, as
            // the official type will be undefined, not null.
            var officialType = originalTypeMap[type.name];
            if (officialType && type !== officialType) {
                return officialType;
            }
        }
        return type;
    }
}
// TODO:
// consider removing the default level of pruning in v7
//
// Pruning was introduced into healSchema in v5, so legacy schema directives relying on pruning
// during healing are likely to be rare. pruning is now recommended via the dedicated pruneSchema
// function which does not force pruning on library users and gives granular control in terms of
// pruning types. pruneSchema does recreate the schema -- a parallel version that prunes in place
// could be considered.
function pruneTypes$1(typeMap, directives) {
    var implementedInterfaces = {};
    Object.values(typeMap).forEach(function (namedType) {
        if ('getInterfaces' in namedType) {
            namedType.getInterfaces().forEach(function (iface) {
                implementedInterfaces[iface.name] = true;
            });
        }
    });
    var prunedTypeMap = false;
    var typeNames = Object.keys(typeMap);
    for (var i = 0; i < typeNames.length; i++) {
        var typeName = typeNames[i];
        var type = typeMap[typeName];
        if (graphql.isObjectType(type) || graphql.isInputObjectType(type)) {
            // prune types with no fields
            if (!Object.keys(type.getFields()).length) {
                typeMap[typeName] = null;
                prunedTypeMap = true;
            }
        }
        else if (graphql.isUnionType(type)) {
            // prune unions without underlying types
            if (!type.getTypes().length) {
                typeMap[typeName] = null;
                prunedTypeMap = true;
            }
        }
        else if (graphql.isInterfaceType(type)) {
            // prune interfaces without fields or without implementations
            if (!Object.keys(type.getFields()).length || !(type.name in implementedInterfaces)) {
                typeMap[typeName] = null;
                prunedTypeMap = true;
            }
        }
    }
    // every prune requires another round of healing
    if (prunedTypeMap) {
        healTypes(typeMap, directives);
    }
}

// Abstract base class of any visitor implementation, defining the available
// visitor methods along with their parameter types, and providing a static
// helper function for determining whether a subclass implements a given
// visitor method, as opposed to inheriting one of the stubs defined here.
var SchemaVisitor = /** @class */ (function () {
    function SchemaVisitor() {
    }
    // Determine if this SchemaVisitor (sub)class implements a particular
    // visitor method.
    SchemaVisitor.implementsVisitorMethod = function (methodName) {
        if (!methodName.startsWith('visit')) {
            return false;
        }
        var method = this.prototype[methodName];
        if (typeof method !== 'function') {
            return false;
        }
        if (this.name === 'SchemaVisitor') {
            // The SchemaVisitor class implements every visitor method.
            return true;
        }
        var stub = SchemaVisitor.prototype[methodName];
        if (method === stub) {
            // If this.prototype[methodName] was just inherited from SchemaVisitor,
            // then this class does not really implement the method.
            return false;
        }
        return true;
    };
    // Concrete subclasses of SchemaVisitor should override one or more of these
    // visitor methods, in order to express their interest in handling certain
    // schema types/locations. Each method may return null to remove the given
    // type from the schema, a non-null value of the same type to update the
    // type in the schema, or nothing to leave the type as it was.
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    SchemaVisitor.prototype.visitSchema = function (_schema) { };
    SchemaVisitor.prototype.visitScalar = function (_scalar
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitObject = function (_object
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitFieldDefinition = function (_field, _details
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitArgumentDefinition = function (_argument, _details
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitInterface = function (_iface
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    SchemaVisitor.prototype.visitUnion = function (_union) { };
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    SchemaVisitor.prototype.visitEnum = function (_type) { };
    SchemaVisitor.prototype.visitEnumValue = function (_value, _details
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitInputObject = function (_object
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    SchemaVisitor.prototype.visitInputFieldDefinition = function (_field, _details
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    ) { };
    return SchemaVisitor;
}());

function isSchemaVisitor(obj) {
    if ('schema' in obj && graphql.isSchema(obj.schema)) {
        if ('visitSchema' in obj && typeof obj.visitSchema === 'function') {
            return true;
        }
    }
    return false;
}
// Generic function for visiting GraphQLSchema objects.
function visitSchema(schema, 
// To accommodate as many different visitor patterns as possible, the
// visitSchema function does not simply accept a single instance of the
// SchemaVisitor class, but instead accepts a function that takes the
// current VisitableSchemaType object and the name of a visitor method and
// returns an array of SchemaVisitor instances that implement the visitor
// method and have an interest in handling the given VisitableSchemaType
// object. In the simplest case, this function can always return an array
// containing a single visitor object, without even looking at the type or
// methodName parameters. In other cases, this function might sometimes
// return an empty array to indicate there are no visitors that should be
// applied to the given VisitableSchemaType object. For an example of a
// visitor pattern that benefits from this abstraction, see the
// SchemaDirectiveVisitor class below.
visitorOrVisitorSelector) {
    var visitorSelector = typeof visitorOrVisitorSelector === 'function' ? visitorOrVisitorSelector : function () { return visitorOrVisitorSelector; };
    // Helper function that calls visitorSelector and applies the resulting
    // visitors to the given type, with arguments [type, ...args].
    function callMethod(methodName, type) {
        var args = [];
        for (var _i = 2; _i < arguments.length; _i++) {
            args[_i - 2] = arguments[_i];
        }
        var visitors = visitorSelector(type, methodName);
        visitors = Array.isArray(visitors) ? visitors : [visitors];
        var finalType = type;
        visitors.every(function (visitorOrVisitorDef) {
            var newType;
            if (isSchemaVisitor(visitorOrVisitorDef)) {
                newType = visitorOrVisitorDef[methodName].apply(visitorOrVisitorDef, tslib.__spread([finalType], args));
            }
            else if (graphql.isNamedType(finalType) &&
                (methodName === 'visitScalar' ||
                    methodName === 'visitEnum' ||
                    methodName === 'visitObject' ||
                    methodName === 'visitInputObject' ||
                    methodName === 'visitUnion' ||
                    methodName === 'visitInterface')) {
                var specifiers = getTypeSpecifiers$1(finalType, schema);
                var typeVisitor = getVisitor(visitorOrVisitorDef, specifiers);
                newType = typeVisitor != null ? typeVisitor(finalType, schema) : undefined;
            }
            if (typeof newType === 'undefined') {
                // Keep going without modifying type.
                return true;
            }
            if (methodName === 'visitSchema' || graphql.isSchema(finalType)) {
                throw new Error("Method " + methodName + " cannot replace schema with " + newType);
            }
            if (newType === null) {
                // Stop the loop and return null form callMethod, which will cause
                // the type to be removed from the schema.
                finalType = null;
                return false;
            }
            // Update type to the new type returned by the visitor method, so that
            // later directives will see the new type, and callMethod will return
            // the final type.
            finalType = newType;
            return true;
        });
        // If there were no directives for this type object, or if all visitor
        // methods returned nothing, type will be returned unmodified.
        return finalType;
    }
    // Recursive helper function that calls any appropriate visitor methods for
    // each object in the schema, then traverses the object's children (if any).
    function visit(type) {
        var e_1, _a;
        if (graphql.isSchema(type)) {
            // Unlike the other types, the root GraphQLSchema object cannot be
            // replaced by visitor methods, because that would make life very hard
            // for SchemaVisitor subclasses that rely on the original schema object.
            callMethod('visitSchema', type);
            var typeMap_1 = type.getTypeMap();
            Object.entries(typeMap_1).forEach(function (_a) {
                var _b = tslib.__read(_a, 2), typeName = _b[0], namedType = _b[1];
                if (!typeName.startsWith('__') && namedType != null) {
                    // Call visit recursively to let it determine which concrete
                    // subclass of GraphQLNamedType we found in the type map.
                    // We do not use updateEachKey because we want to preserve
                    // deleted types in the typeMap so that other types that reference
                    // the deleted types can be healed.
                    typeMap_1[typeName] = visit(namedType);
                }
            });
            return type;
        }
        if (graphql.isObjectType(type)) {
            // Note that callMethod('visitObject', type) may not actually call any
            // methods, if there are no @directive annotations associated with this
            // type, or if this SchemaDirectiveVisitor subclass does not override
            // the visitObject method.
            var newObject = callMethod('visitObject', type);
            if (newObject != null) {
                visitFields(newObject);
            }
            return newObject;
        }
        if (graphql.isInterfaceType(type)) {
            var newInterface = callMethod('visitInterface', type);
            if (newInterface != null) {
                visitFields(newInterface);
            }
            return newInterface;
        }
        if (graphql.isInputObjectType(type)) {
            var newInputObject = callMethod('visitInputObject', type);
            if (newInputObject != null) {
                var fieldMap = newInputObject.getFields();
                try {
                    for (var _b = tslib.__values(Object.keys(fieldMap)), _c = _b.next(); !_c.done; _c = _b.next()) {
                        var key = _c.value;
                        fieldMap[key] = callMethod('visitInputFieldDefinition', fieldMap[key], {
                            // Since we call a different method for input object fields, we
                            // can't reuse the visitFields function here.
                            objectType: newInputObject,
                        });
                        if (!fieldMap[key]) {
                            delete fieldMap[key];
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
            }
            return newInputObject;
        }
        if (graphql.isScalarType(type)) {
            return callMethod('visitScalar', type);
        }
        if (graphql.isUnionType(type)) {
            return callMethod('visitUnion', type);
        }
        if (graphql.isEnumType(type)) {
            var newEnum_1 = callMethod('visitEnum', type);
            if (newEnum_1 != null) {
                var newValues = newEnum_1
                    .getValues()
                    .map(function (value) {
                    return callMethod('visitEnumValue', value, {
                        enumType: newEnum_1,
                    });
                })
                    .filter(Boolean);
                // Recreate the enum type if any of the values changed
                var valuesUpdated = newValues.some(function (value, index) { return value !== newEnum_1.getValues()[index]; });
                if (valuesUpdated) {
                    newEnum_1 = new graphql.GraphQLEnumType(tslib.__assign(tslib.__assign({}, newEnum_1.toConfig()), { values: newValues.reduce(function (prev, value) {
                            var _a;
                            return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[value.name] = {
                                value: value.value,
                                deprecationReason: value.deprecationReason,
                                description: value.description,
                                astNode: value.astNode,
                            }, _a)));
                        }, {}) }));
                }
            }
            return newEnum_1;
        }
        throw new Error("Unexpected schema type: " + type);
    }
    function visitFields(type) {
        var e_2, _a;
        var fieldMap = type.getFields();
        var _loop_1 = function (key, field) {
            // It would be nice if we could call visit(field) recursively here, but
            // GraphQLField is merely a type, not a value that can be detected using
            // an instanceof check, so we have to visit the fields in this lexical
            // context, so that TypeScript can validate the call to
            // visitFieldDefinition.
            var newField = callMethod('visitFieldDefinition', field, {
                // While any field visitor needs a reference to the field object, some
                // field visitors may also need to know the enclosing (parent) type,
                // perhaps to determine if the parent is a GraphQLObjectType or a
                // GraphQLInterfaceType. To obtain a reference to the parent, a
                // visitor method can have a second parameter, which will be an object
                // with an .objectType property referring to the parent.
                objectType: type,
            });
            if (newField.args != null) {
                newField.args = newField.args
                    .map(function (arg) {
                    return callMethod('visitArgumentDefinition', arg, {
                        // Like visitFieldDefinition, visitArgumentDefinition takes a
                        // second parameter that provides additional context, namely the
                        // parent .field and grandparent .objectType. Remember that the
                        // current GraphQLSchema is always available via this.schema.
                        field: newField,
                        objectType: type,
                    });
                })
                    .filter(Boolean);
            }
            // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
            if (newField) {
                fieldMap[key] = newField;
            }
            else {
                delete fieldMap[key];
            }
        };
        try {
            for (var _b = tslib.__values(Object.entries(fieldMap)), _c = _b.next(); !_c.done; _c = _b.next()) {
                var _d = tslib.__read(_c.value, 2), key = _d[0], field = _d[1];
                _loop_1(key, field);
            }
        }
        catch (e_2_1) { e_2 = { error: e_2_1 }; }
        finally {
            try {
                if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
            }
            finally { if (e_2) throw e_2.error; }
        }
    }
    visit(schema);
    // Automatically update any references to named schema types replaced
    // during the traversal, so implementors don't have to worry about that.
    healSchema(schema);
    // Return schema for convenience, even though schema parameter has all updated types.
    return schema;
}
function getTypeSpecifiers$1(type, schema) {
    var specifiers = [exports.VisitSchemaKind.TYPE];
    if (graphql.isObjectType(type)) {
        specifiers.push(exports.VisitSchemaKind.COMPOSITE_TYPE, exports.VisitSchemaKind.OBJECT_TYPE);
        var query = schema.getQueryType();
        var mutation = schema.getMutationType();
        var subscription = schema.getSubscriptionType();
        if (type === query) {
            specifiers.push(exports.VisitSchemaKind.ROOT_OBJECT, exports.VisitSchemaKind.QUERY);
        }
        else if (type === mutation) {
            specifiers.push(exports.VisitSchemaKind.ROOT_OBJECT, exports.VisitSchemaKind.MUTATION);
        }
        else if (type === subscription) {
            specifiers.push(exports.VisitSchemaKind.ROOT_OBJECT, exports.VisitSchemaKind.SUBSCRIPTION);
        }
    }
    else if (graphql.isInputType(type)) {
        specifiers.push(exports.VisitSchemaKind.INPUT_OBJECT_TYPE);
    }
    else if (graphql.isInterfaceType(type)) {
        specifiers.push(exports.VisitSchemaKind.COMPOSITE_TYPE, exports.VisitSchemaKind.ABSTRACT_TYPE, exports.VisitSchemaKind.INTERFACE_TYPE);
    }
    else if (graphql.isUnionType(type)) {
        specifiers.push(exports.VisitSchemaKind.COMPOSITE_TYPE, exports.VisitSchemaKind.ABSTRACT_TYPE, exports.VisitSchemaKind.UNION_TYPE);
    }
    else if (graphql.isEnumType(type)) {
        specifiers.push(exports.VisitSchemaKind.ENUM_TYPE);
    }
    else if (graphql.isScalarType(type)) {
        specifiers.push(exports.VisitSchemaKind.SCALAR_TYPE);
    }
    return specifiers;
}
function getVisitor(visitorDef, specifiers) {
    var typeVisitor;
    var stack = tslib.__spread(specifiers);
    while (!typeVisitor && stack.length > 0) {
        var next = stack.pop();
        typeVisitor = visitorDef[next];
    }
    return typeVisitor != null ? typeVisitor : null;
}

// This class represents a reusable implementation of a @directive that may
// appear in a GraphQL schema written in Schema Definition Language.
//
// By overriding one or more visit{Object,Union,...} methods, a subclass
// registers interest in certain schema types, such as GraphQLObjectType,
// GraphQLUnionType, etc. When SchemaDirectiveVisitor.visitSchemaDirectives is
// called with a GraphQLSchema object and a map of visitor subclasses, the
// overidden methods of those subclasses allow the visitors to obtain
// references to any type objects that have @directives attached to them,
// enabling visitors to inspect or modify the schema as appropriate.
//
// For example, if a directive called @rest(url: "...") appears after a field
// definition, a SchemaDirectiveVisitor subclass could provide meaning to that
// directive by overriding the visitFieldDefinition method (which receives a
// GraphQLField parameter), and then the body of that visitor method could
// manipulate the field's resolver function to fetch data from a REST endpoint
// described by the url argument passed to the @rest directive:
//
//   const typeDefs = `
//   type Query {
//     people: [Person] @rest(url: "/api/v1/people")
//   }`;
//
//   const schema = makeExecutableSchema({ typeDefs });
//
//   SchemaDirectiveVisitor.visitSchemaDirectives(schema, {
//     rest: class extends SchemaDirectiveVisitor {
//       public visitFieldDefinition(field: GraphQLField<any, any>) {
//         const { url } = this.args;
//         field.resolve = () => fetch(url);
//       }
//     }
//   });
//
// The subclass in this example is defined as an anonymous class expression,
// for brevity. A truly reusable SchemaDirectiveVisitor would most likely be
// defined in a library using a named class declaration, and then exported for
// consumption by other modules and packages.
//
// See below for a complete list of overridable visitor methods, their
// parameter types, and more details about the properties exposed by instances
// of the SchemaDirectiveVisitor class.
var SchemaDirectiveVisitor = /** @class */ (function (_super) {
    tslib.__extends(SchemaDirectiveVisitor, _super);
    // Mark the constructor protected to enforce passing SchemaDirectiveVisitor
    // subclasses (not instances) to visitSchemaDirectives.
    function SchemaDirectiveVisitor(config) {
        var _this = _super.call(this) || this;
        _this.name = config.name;
        _this.args = config.args;
        _this.visitedType = config.visitedType;
        _this.schema = config.schema;
        _this.context = config.context;
        return _this;
    }
    // Override this method to return a custom GraphQLDirective (or modify one
    // already present in the schema) to enforce argument types, provide default
    // argument values, or specify schema locations where this @directive may
    // appear. By default, any declaration found in the schema will be returned.
    SchemaDirectiveVisitor.getDirectiveDeclaration = function (directiveName, schema) {
        return schema.getDirective(directiveName);
    };
    // Call SchemaDirectiveVisitor.visitSchemaDirectives to visit every
    // @directive in the schema and create an appropriate SchemaDirectiveVisitor
    // instance to visit the object decorated by the @directive.
    SchemaDirectiveVisitor.visitSchemaDirectives = function (schema, 
    // The keys of this object correspond to directive names as they appear
    // in the schema, and the values should be subclasses (not instances!)
    // of the SchemaDirectiveVisitor class. This distinction is important
    // because a new SchemaDirectiveVisitor instance will be created each
    // time a matching directive is found in the schema AST, with arguments
    // and other metadata specific to that occurrence. To help prevent the
    // mistake of passing instances, the SchemaDirectiveVisitor constructor
    // method is marked as protected.
    directiveVisitors, 
    // Optional context object that will be available to all visitor instances
    // via this.context. Defaults to an empty null-prototype object.
    context
    // The visitSchemaDirectives method returns a map from directive names to
    // lists of SchemaDirectiveVisitors created while visiting the schema.
    ) {
        if (context === void 0) { context = Object.create(null); }
        // If the schema declares any directives for public consumption, record
        // them here so that we can properly coerce arguments when/if we encounter
        // an occurrence of the directive while walking the schema below.
        var declaredDirectives = this.getDeclaredDirectives(schema, directiveVisitors);
        // Map from directive names to lists of SchemaDirectiveVisitor instances
        // created while visiting the schema.
        var createdVisitors = Object.keys(directiveVisitors).reduce(function (prev, item) {
            var _a;
            return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[item] = [], _a)));
        }, {});
        var directiveVisitorMap = Object.entries(directiveVisitors).reduce(function (prev, _a) {
            var _b;
            var _c = tslib.__read(_a, 2), key = _c[0], value = _c[1];
            return (tslib.__assign(tslib.__assign({}, prev), (_b = {}, _b[key] = value, _b)));
        }, {});
        function visitorSelector(type, methodName) {
            var _a, _b;
            var directiveNodes = (_b = (_a = type === null || type === void 0 ? void 0 : type.astNode) === null || _a === void 0 ? void 0 : _a.directives) !== null && _b !== void 0 ? _b : [];
            var extensionASTNodes = type.extensionASTNodes;
            if (extensionASTNodes != null) {
                extensionASTNodes.forEach(function (extensionASTNode) {
                    if (extensionASTNode.directives != null) {
                        directiveNodes = directiveNodes.concat(extensionASTNode.directives);
                    }
                });
            }
            var visitors = [];
            directiveNodes.forEach(function (directiveNode) {
                var directiveName = directiveNode.name.value;
                if (!(directiveName in directiveVisitorMap)) {
                    return;
                }
                var VisitorClass = directiveVisitorMap[directiveName];
                // Avoid creating visitor objects if visitorClass does not override
                // the visitor method named by methodName.
                if (!VisitorClass.implementsVisitorMethod(methodName)) {
                    return;
                }
                var decl = declaredDirectives[directiveName];
                var args;
                if (decl != null) {
                    // If this directive was explicitly declared, use the declared
                    // argument types (and any default values) to check, coerce, and/or
                    // supply default values for the given arguments.
                    args = getArgumentValues(decl, directiveNode);
                }
                else {
                    // If this directive was not explicitly declared, just convert the
                    // argument nodes to their corresponding JavaScript values.
                    args = Object.create(null);
                    if (directiveNode.arguments != null) {
                        directiveNode.arguments.forEach(function (arg) {
                            args[arg.name.value] = graphql.valueFromASTUntyped(arg.value);
                        });
                    }
                }
                // As foretold in comments near the top of the visitSchemaDirectives
                // method, this is where instances of the SchemaDirectiveVisitor class
                // get created and assigned names. While subclasses could override the
                // constructor method, the constructor is marked as protected, so
                // these are the only arguments that will ever be passed.
                visitors.push(new VisitorClass({
                    name: directiveName,
                    args: args,
                    visitedType: type,
                    schema: schema,
                    context: context,
                }));
            });
            if (visitors.length > 0) {
                visitors.forEach(function (visitor) {
                    createdVisitors[visitor.name].push(visitor);
                });
            }
            return visitors;
        }
        visitSchema(schema, visitorSelector);
        return createdVisitors;
    };
    SchemaDirectiveVisitor.getDeclaredDirectives = function (schema, directiveVisitors) {
        var declaredDirectives = schema.getDirectives().reduce(function (prev, curr) {
            var _a;
            return (tslib.__assign(tslib.__assign({}, prev), (_a = {}, _a[curr.name] = curr, _a)));
        }, {});
        // If the visitor subclass overrides getDirectiveDeclaration, and it
        // returns a non-null GraphQLDirective, use that instead of any directive
        // declared in the schema itself. Reasoning: if a SchemaDirectiveVisitor
        // goes to the trouble of implementing getDirectiveDeclaration, it should
        // be able to rely on that implementation.
        Object.entries(directiveVisitors).forEach(function (_a) {
            var _b = tslib.__read(_a, 2), directiveName = _b[0], visitorClass = _b[1];
            var decl = visitorClass.getDirectiveDeclaration(directiveName, schema);
            if (decl != null) {
                declaredDirectives[directiveName] = decl;
            }
        });
        Object.entries(declaredDirectives).forEach(function (_a) {
            var _b = tslib.__read(_a, 2), name = _b[0], decl = _b[1];
            if (!(name in directiveVisitors)) {
                // SchemaDirectiveVisitors.visitSchemaDirectives might be called
                // multiple times with partial directiveVisitors maps, so it's not
                // necessarily an error for directiveVisitors to be missing an
                // implementation of a directive that was declared in the schema.
                return;
            }
            var visitorClass = directiveVisitors[name];
            decl.locations.forEach(function (loc) {
                var visitorMethodName = directiveLocationToVisitorMethodName(loc);
                if (SchemaVisitor.implementsVisitorMethod(visitorMethodName) &&
                    !visitorClass.implementsVisitorMethod(visitorMethodName)) {
                    // While visitor subclasses may implement extra visitor methods,
                    // it's definitely a mistake if the GraphQLDirective declares itself
                    // applicable to certain schema locations, and the visitor subclass
                    // does not implement all the corresponding methods.
                    throw new Error("SchemaDirectiveVisitor for @" + name + " must implement " + visitorMethodName + " method");
                }
            });
        });
        return declaredDirectives;
    };
    return SchemaDirectiveVisitor;
}(SchemaVisitor));
// Convert a string like "FIELD_DEFINITION" to "visitFieldDefinition".
function directiveLocationToVisitorMethodName(loc) {
    return ('visit' +
        loc.replace(/([^_]*)_?/g, function (_wholeMatch, part) { return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase(); }));
}

function getResolversFromSchema(schema) {
    var resolvers = Object.create({});
    var typeMap = schema.getTypeMap();
    Object.keys(typeMap).forEach(function (typeName) {
        var type = typeMap[typeName];
        if (graphql.isScalarType(type)) {
            if (!graphql.isSpecifiedScalarType(type)) {
                var config = type.toConfig();
                delete config.astNode; // avoid AST duplication elsewhere
                resolvers[typeName] = new graphql.GraphQLScalarType(config);
            }
        }
        else if (graphql.isEnumType(type)) {
            resolvers[typeName] = {};
            var values = type.getValues();
            values.forEach(function (value) {
                resolvers[typeName][value.name] = value.value;
            });
        }
        else if (graphql.isInterfaceType(type)) {
            if (type.resolveType != null) {
                resolvers[typeName] = {
                    __resolveType: type.resolveType,
                };
            }
        }
        else if (graphql.isUnionType(type)) {
            if (type.resolveType != null) {
                resolvers[typeName] = {
                    __resolveType: type.resolveType,
                };
            }
        }
        else if (graphql.isObjectType(type)) {
            resolvers[typeName] = {};
            if (type.isTypeOf != null) {
                resolvers[typeName].__isTypeOf = type.isTypeOf;
            }
            var fields_1 = type.getFields();
            Object.keys(fields_1).forEach(function (fieldName) {
                var field = fields_1[fieldName];
                resolvers[typeName][fieldName] = {
                    resolve: field.resolve,
                    subscribe: field.subscribe,
                };
            });
        }
    });
    return resolvers;
}

function forEachField(schema, fn) {
    var typeMap = schema.getTypeMap();
    Object.keys(typeMap).forEach(function (typeName) {
        var type = typeMap[typeName];
        // TODO: maybe have an option to include these?
        if (!graphql.getNamedType(type).name.startsWith('__') && graphql.isObjectType(type)) {
            var fields_1 = type.getFields();
            Object.keys(fields_1).forEach(function (fieldName) {
                var field = fields_1[fieldName];
                fn(field, typeName, fieldName);
            });
        }
    });
}

function forEachDefaultValue(schema, fn) {
    var typeMap = schema.getTypeMap();
    Object.keys(typeMap).forEach(function (typeName) {
        var type = typeMap[typeName];
        if (!graphql.getNamedType(type).name.startsWith('__')) {
            if (graphql.isObjectType(type)) {
                var fields_1 = type.getFields();
                Object.keys(fields_1).forEach(function (fieldName) {
                    var field = fields_1[fieldName];
                    field.args.forEach(function (arg) {
                        arg.defaultValue = fn(arg.type, arg.defaultValue);
                    });
                });
            }
            else if (graphql.isInputObjectType(type)) {
                var fields_2 = type.getFields();
                Object.keys(fields_2).forEach(function (fieldName) {
                    var field = fields_2[fieldName];
                    field.defaultValue = fn(field.type, field.defaultValue);
                });
            }
        }
    });
}

// addTypes uses toConfig to create a new schema with a new or replaced
function addTypes(schema, newTypesOrDirectives) {
    var queryType = schema.getQueryType();
    var mutationType = schema.getMutationType();
    var subscriptionType = schema.getSubscriptionType();
    var queryTypeName = queryType != null ? queryType.name : undefined;
    var mutationTypeName = mutationType != null ? mutationType.name : undefined;
    var subscriptionTypeName = subscriptionType != null ? subscriptionType.name : undefined;
    var config = schema.toConfig();
    var originalTypeMap = {};
    config.types.forEach(function (type) {
        originalTypeMap[type.name] = type;
    });
    var originalDirectiveMap = {};
    config.directives.forEach(function (directive) {
        originalDirectiveMap[directive.name] = directive;
    });
    newTypesOrDirectives.forEach(function (newTypeOrDirective) {
        if (graphql.isNamedType(newTypeOrDirective)) {
            originalTypeMap[newTypeOrDirective.name] = newTypeOrDirective;
        }
        else if (graphql.isDirective(newTypeOrDirective)) {
            originalDirectiveMap[newTypeOrDirective.name] = newTypeOrDirective;
        }
    });
    var _a = rewireTypes(originalTypeMap, Object.keys(originalDirectiveMap).map(function (directiveName) { return originalDirectiveMap[directiveName]; })), typeMap = _a.typeMap, directives = _a.directives;
    return new graphql.GraphQLSchema(tslib.__assign(tslib.__assign({}, config), { query: queryTypeName ? typeMap[queryTypeName] : undefined, mutation: mutationTypeName ? typeMap[mutationTypeName] : undefined, subscription: subscriptionTypeName != null ? typeMap[subscriptionTypeName] : undefined, types: Object.keys(typeMap).map(function (typeName) { return typeMap[typeName]; }), directives: directives }));
}

/**
 * Prunes the provided schema, removing unused and empty types
 * @param schema The schema to prune
 * @param options Additional options for removing unused types from the schema
 */
function pruneSchema(schema, options) {
    var _a;
    if (options === void 0) { options = {}; }
    var pruningContext = {
        schema: schema,
        unusedTypes: Object.create(null),
        implementations: Object.create(null),
    };
    Object.keys(schema.getTypeMap()).forEach(function (typeName) {
        var type = schema.getType(typeName);
        if ('getInterfaces' in type) {
            type.getInterfaces().forEach(function (iface) {
                if (pruningContext.implementations[iface.name] == null) {
                    pruningContext.implementations[iface.name] = Object.create(null);
                }
                pruningContext.implementations[iface.name][type.name] = true;
            });
        }
    });
    visitTypes(pruningContext, schema);
    return mapSchema(schema, (_a = {},
        _a[exports.MapperKind.TYPE] = function (type) {
            if (graphql.isObjectType(type) || graphql.isInputObjectType(type)) {
                if ((!Object.keys(type.getFields()).length && !options.skipEmptyCompositeTypePruning) ||
                    (pruningContext.unusedTypes[type.name] && !options.skipUnusedTypesPruning)) {
                    return null;
                }
            }
            else if (graphql.isUnionType(type)) {
                if ((!type.getTypes().length && !options.skipEmptyUnionPruning) ||
                    (pruningContext.unusedTypes[type.name] && !options.skipUnusedTypesPruning)) {
                    return null;
                }
            }
            else if (graphql.isInterfaceType(type)) {
                if ((!Object.keys(type.getFields()).length && !options.skipEmptyCompositeTypePruning) ||
                    (!Object.keys(pruningContext.implementations[type.name]).length &&
                        !options.skipUnimplementedInterfacesPruning) ||
                    (pruningContext.unusedTypes[type.name] && !options.skipUnusedTypesPruning)) {
                    return null;
                }
            }
            else {
                if (pruningContext.unusedTypes[type.name] && !options.skipUnusedTypesPruning) {
                    return null;
                }
            }
        },
        _a));
}
function visitOutputType(visitedTypes, pruningContext, type) {
    if (visitedTypes[type.name]) {
        return;
    }
    visitedTypes[type.name] = true;
    pruningContext.unusedTypes[type.name] = false;
    if (graphql.isObjectType(type) || graphql.isInterfaceType(type)) {
        var fields_1 = type.getFields();
        Object.keys(fields_1).forEach(function (fieldName) {
            var field = fields_1[fieldName];
            var namedType = graphql.getNamedType(field.type);
            visitOutputType(visitedTypes, pruningContext, namedType);
            var args = field.args;
            args.forEach(function (arg) {
                var type = graphql.getNamedType(arg.type);
                visitInputType(visitedTypes, pruningContext, type);
            });
        });
        if (graphql.isInterfaceType(type)) {
            Object.keys(pruningContext.implementations[type.name]).forEach(function (typeName) {
                visitOutputType(visitedTypes, pruningContext, pruningContext.schema.getType(typeName));
            });
        }
        if ('getInterfaces' in type) {
            type.getInterfaces().forEach(function (type) {
                visitOutputType(visitedTypes, pruningContext, type);
            });
        }
    }
    else if (graphql.isUnionType(type)) {
        var types = type.getTypes();
        types.forEach(function (type) { return visitOutputType(visitedTypes, pruningContext, type); });
    }
}
function visitInputType(visitedTypes, pruningContext, type) {
    if (visitedTypes[type.name]) {
        return;
    }
    pruningContext.unusedTypes[type.name] = false;
    visitedTypes[type.name] = true;
    if (graphql.isInputObjectType(type)) {
        var fields_2 = type.getFields();
        Object.keys(fields_2).forEach(function (fieldName) {
            var field = fields_2[fieldName];
            var namedType = graphql.getNamedType(field.type);
            visitInputType(visitedTypes, pruningContext, namedType);
        });
    }
}
function visitTypes(pruningContext, schema) {
    Object.keys(schema.getTypeMap()).forEach(function (typeName) {
        if (!typeName.startsWith('__')) {
            pruningContext.unusedTypes[typeName] = true;
        }
    });
    var visitedTypes = Object.create(null);
    var rootTypes = [schema.getQueryType(), schema.getMutationType(), schema.getSubscriptionType()].filter(function (type) { return type != null; });
    rootTypes.forEach(function (rootType) { return visitOutputType(visitedTypes, pruningContext, rootType); });
    schema.getDirectives().forEach(function (directive) {
        directive.args.forEach(function (arg) {
            var type = graphql.getNamedType(arg.type);
            visitInputType(visitedTypes, pruningContext, type);
        });
    });
}

function mergeDeep(target) {
    var e_1, _a, _b, _c;
    var sources = [];
    for (var _i = 1; _i < arguments.length; _i++) {
        sources[_i - 1] = arguments[_i];
    }
    if (graphql.isScalarType(target)) {
        return target;
    }
    var output = tslib.__assign({}, target);
    try {
        for (var sources_1 = tslib.__values(sources), sources_1_1 = sources_1.next(); !sources_1_1.done; sources_1_1 = sources_1.next()) {
            var source = sources_1_1.value;
            if (isObject(target) && isObject(source)) {
                for (var key in source) {
                    if (isObject(source[key])) {
                        if (!(key in target)) {
                            Object.assign(output, (_b = {}, _b[key] = source[key], _b));
                        }
                        else {
                            output[key] = mergeDeep(target[key], source[key]);
                        }
                    }
                    else {
                        Object.assign(output, (_c = {}, _c[key] = source[key], _c));
                    }
                }
            }
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (sources_1_1 && !sources_1_1.done && (_a = sources_1.return)) _a.call(sources_1);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return output;
}
function isObject(item) {
    return item && typeof item === 'object' && !Array.isArray(item);
}

function renameFieldNode(fieldNode, name) {
    return tslib.__assign(tslib.__assign({}, fieldNode), { alias: {
            kind: graphql.Kind.NAME,
            value: fieldNode.alias != null ? fieldNode.alias.value : fieldNode.name.value,
        }, name: {
            kind: graphql.Kind.NAME,
            value: name,
        } });
}
function preAliasFieldNode(fieldNode, str) {
    return tslib.__assign(tslib.__assign({}, fieldNode), { alias: {
            kind: graphql.Kind.NAME,
            value: "" + str + (fieldNode.alias != null ? fieldNode.alias.value : fieldNode.name.value),
        } });
}
function wrapFieldNode(fieldNode, path) {
    var newFieldNode = fieldNode;
    path.forEach(function (fieldName) {
        newFieldNode = {
            kind: graphql.Kind.FIELD,
            name: {
                kind: graphql.Kind.NAME,
                value: fieldName,
            },
            selectionSet: {
                kind: graphql.Kind.SELECTION_SET,
                selections: [fieldNode],
            },
        };
    });
    return newFieldNode;
}
function collectFields(selectionSet, fragments, fields, visitedFragmentNames) {
    if (fields === void 0) { fields = []; }
    if (visitedFragmentNames === void 0) { visitedFragmentNames = {}; }
    if (selectionSet != null) {
        selectionSet.selections.forEach(function (selection) {
            switch (selection.kind) {
                case graphql.Kind.FIELD:
                    fields.push(selection);
                    break;
                case graphql.Kind.INLINE_FRAGMENT:
                    collectFields(selection.selectionSet, fragments, fields, visitedFragmentNames);
                    break;
                case graphql.Kind.FRAGMENT_SPREAD: {
                    var fragmentName = selection.name.value;
                    if (!visitedFragmentNames[fragmentName]) {
                        visitedFragmentNames[fragmentName] = true;
                        collectFields(fragments[fragmentName].selectionSet, fragments, fields, visitedFragmentNames);
                    }
                    break;
                }
            }
        });
    }
    return fields;
}
function hoistFieldNodes(_a) {
    var fieldNode = _a.fieldNode, fieldNames = _a.fieldNames, _b = _a.path, path = _b === void 0 ? [] : _b, _c = _a.delimeter, delimeter = _c === void 0 ? '__gqltf__' : _c, fragments = _a.fragments;
    var alias = fieldNode.alias != null ? fieldNode.alias.value : fieldNode.name.value;
    var newFieldNodes = [];
    if (path.length) {
        var remainingPathSegments_1 = path.slice();
        var initialPathSegment_1 = remainingPathSegments_1.shift();
        collectFields(fieldNode.selectionSet, fragments).forEach(function (possibleFieldNode) {
            if (possibleFieldNode.name.value === initialPathSegment_1) {
                newFieldNodes = newFieldNodes.concat(hoistFieldNodes({
                    fieldNode: preAliasFieldNode(possibleFieldNode, "" + alias + delimeter),
                    fieldNames: fieldNames,
                    path: remainingPathSegments_1,
                    delimeter: delimeter,
                    fragments: fragments,
                }));
            }
        });
    }
    else {
        collectFields(fieldNode.selectionSet, fragments).forEach(function (possibleFieldNode) {
            if (!fieldNames || fieldNames.includes(possibleFieldNode.name.value)) {
                newFieldNodes.push(preAliasFieldNode(possibleFieldNode, "" + alias + delimeter));
            }
        });
    }
    return newFieldNodes;
}

function concatInlineFragments(type, fragments) {
    var fragmentSelections = fragments.reduce(function (selections, fragment) { return selections.concat(fragment.selectionSet.selections); }, []);
    var deduplicatedFragmentSelection = deduplicateSelection(fragmentSelections);
    return {
        kind: graphql.Kind.INLINE_FRAGMENT,
        typeCondition: {
            kind: graphql.Kind.NAMED_TYPE,
            name: {
                kind: graphql.Kind.NAME,
                value: type,
            },
        },
        selectionSet: {
            kind: graphql.Kind.SELECTION_SET,
            selections: deduplicatedFragmentSelection,
        },
    };
}
function deduplicateSelection(nodes) {
    var selectionMap = nodes.reduce(function (map, node) {
        var _a, _b, _c;
        switch (node.kind) {
            case 'Field': {
                if (node.alias != null) {
                    if (node.alias.value in map) {
                        return map;
                    }
                    return tslib.__assign(tslib.__assign({}, map), (_a = {}, _a[node.alias.value] = node, _a));
                }
                if (node.name.value in map) {
                    return map;
                }
                return tslib.__assign(tslib.__assign({}, map), (_b = {}, _b[node.name.value] = node, _b));
            }
            case 'FragmentSpread': {
                if (node.name.value in map) {
                    return map;
                }
                return tslib.__assign(tslib.__assign({}, map), (_c = {}, _c[node.name.value] = node, _c));
            }
            case 'InlineFragment': {
                if (map.__fragment != null) {
                    var fragment = map.__fragment;
                    return tslib.__assign(tslib.__assign({}, map), { __fragment: concatInlineFragments(fragment.typeCondition.name.value, [fragment, node]) });
                }
                return tslib.__assign(tslib.__assign({}, map), { __fragment: node });
            }
            default: {
                return map;
            }
        }
    }, Object.create(null));
    var selection = Object.keys(selectionMap).reduce(function (selectionList, node) { return selectionList.concat(selectionMap[node]); }, []);
    return selection;
}
function parseFragmentToInlineFragment(definitions) {
    var e_1, _a, e_2, _b;
    if (definitions.trim().startsWith('fragment')) {
        var document_1 = graphql.parse(definitions);
        try {
            for (var _c = tslib.__values(document_1.definitions), _d = _c.next(); !_d.done; _d = _c.next()) {
                var definition = _d.value;
                if (definition.kind === graphql.Kind.FRAGMENT_DEFINITION) {
                    return {
                        kind: graphql.Kind.INLINE_FRAGMENT,
                        typeCondition: definition.typeCondition,
                        selectionSet: definition.selectionSet,
                    };
                }
            }
        }
        catch (e_1_1) { e_1 = { error: e_1_1 }; }
        finally {
            try {
                if (_d && !_d.done && (_a = _c.return)) _a.call(_c);
            }
            finally { if (e_1) throw e_1.error; }
        }
    }
    var query = graphql.parse("{" + definitions + "}").definitions[0];
    try {
        for (var _e = tslib.__values(query.selectionSet.selections), _f = _e.next(); !_f.done; _f = _e.next()) {
            var selection = _f.value;
            if (selection.kind === graphql.Kind.INLINE_FRAGMENT) {
                return selection;
            }
        }
    }
    catch (e_2_1) { e_2 = { error: e_2_1 }; }
    finally {
        try {
            if (_f && !_f.done && (_b = _e.return)) _b.call(_e);
        }
        finally { if (e_2) throw e_2.error; }
    }
    throw new Error('Could not parse fragment');
}

function parseSelectionSet(selectionSet) {
    var query = graphql.parse(selectionSet).definitions[0];
    return query.selectionSet;
}
function typesContainSelectionSet(types, selectionSet) {
    var e_1, _a;
    var fieldMaps = types.map(function (type) { return type.getFields(); });
    var _loop_1 = function (selection) {
        if (selection.kind === graphql.Kind.FIELD) {
            var fields = fieldMaps.map(function (fieldMap) { return fieldMap[selection.name.value]; }).filter(function (field) { return field != null; });
            if (!fields.length) {
                return { value: false };
            }
            if (selection.selectionSet != null) {
                return { value: typesContainSelectionSet(fields.map(function (field) { return graphql.getNamedType(field.type); }), selection.selectionSet) };
            }
        }
        else if (selection.kind === graphql.Kind.INLINE_FRAGMENT && selection.typeCondition.name.value === types[0].name) {
            return { value: typesContainSelectionSet(types, selection.selectionSet) };
        }
    };
    try {
        for (var _b = tslib.__values(selectionSet.selections), _c = _b.next(); !_c.done; _c = _b.next()) {
            var selection = _c.value;
            var state_1 = _loop_1(selection);
            if (typeof state_1 === "object")
                return state_1.value;
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (_c && !_c.done && (_a = _b.return)) _a.call(_b);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return true;
}
function typeContainsSelectionSet(type, selectionSet) {
    var e_2, _a;
    var fields = type.getFields();
    try {
        for (var _b = tslib.__values(selectionSet.selections), _c = _b.next(); !_c.done; _c = _b.next()) {
            var selection = _c.value;
            if (selection.kind === graphql.Kind.FIELD) {
                var field = fields[selection.name.value];
                if (field == null) {
                    return false;
                }
                if (selection.selectionSet != null) {
                    return typeContainsSelectionSet(graphql.getNamedType(field.type), selection.selectionSet);
                }
            }
            else if (selection.kind === graphql.Kind.INLINE_FRAGMENT && selection.typeCondition.name.value === type.name) {
                return typeContainsSelectionSet(type, selection.selectionSet);
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
    return true;
}

/**
 * Get the key under which the result of this resolver will be placed in the response JSON. Basically, just
 * resolves aliases.
 * @param info The info argument to the resolver.
 */
function getResponseKeyFromInfo(info) {
    return info.fieldNodes[0].alias != null ? info.fieldNodes[0].alias.value : info.fieldName;
}

function applySchemaTransforms(originalSchema, transforms) {
    return transforms.reduce(function (schema, transform) {
        return transform.transformSchema != null ? transform.transformSchema(cloneSchema(schema)) : schema;
    }, originalSchema);
}
function applyRequestTransforms(originalRequest, transforms) {
    return transforms.reduce(function (request, transform) {
        return transform.transformRequest != null ? transform.transformRequest(request) : request;
    }, originalRequest);
}
function applyResultTransforms(originalResult, transforms) {
    return transforms.reduceRight(function (result, transform) {
        return transform.transformResult != null ? transform.transformResult(result) : result;
    }, originalResult);
}

function appendObjectFields(schema, typeName, additionalFields) {
    var _a;
    if (schema.getType(typeName) == null) {
        return addTypes(schema, [
            new graphql.GraphQLObjectType({
                name: typeName,
                fields: additionalFields,
            }),
        ]);
    }
    return mapSchema(schema, (_a = {},
        _a[exports.MapperKind.OBJECT_TYPE] = function (type) {
            if (type.name === typeName) {
                var config = type.toConfig();
                var originalFieldConfigMap_1 = config.fields;
                var newFieldConfigMap_1 = {};
                Object.keys(originalFieldConfigMap_1).forEach(function (fieldName) {
                    newFieldConfigMap_1[fieldName] = originalFieldConfigMap_1[fieldName];
                });
                Object.keys(additionalFields).forEach(function (fieldName) {
                    newFieldConfigMap_1[fieldName] = additionalFields[fieldName];
                });
                return correctASTNodes(new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_1 })));
            }
        },
        _a));
}
function removeObjectFields(schema, typeName, testFn) {
    var _a;
    var removedFields = {};
    var newSchema = mapSchema(schema, (_a = {},
        _a[exports.MapperKind.OBJECT_TYPE] = function (type) {
            if (type.name === typeName) {
                var config = type.toConfig();
                var originalFieldConfigMap_2 = config.fields;
                var newFieldConfigMap_2 = {};
                Object.keys(originalFieldConfigMap_2).forEach(function (fieldName) {
                    var originalFieldConfig = originalFieldConfigMap_2[fieldName];
                    if (testFn(fieldName, originalFieldConfig)) {
                        removedFields[fieldName] = originalFieldConfig;
                    }
                    else {
                        newFieldConfigMap_2[fieldName] = originalFieldConfig;
                    }
                });
                return correctASTNodes(new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_2 })));
            }
        },
        _a));
    return [newSchema, removedFields];
}
function selectObjectFields(schema, typeName, testFn) {
    var _a;
    var selectedFields = {};
    mapSchema(schema, (_a = {},
        _a[exports.MapperKind.OBJECT_TYPE] = function (type) {
            if (type.name === typeName) {
                var config = type.toConfig();
                var originalFieldConfigMap_3 = config.fields;
                Object.keys(originalFieldConfigMap_3).forEach(function (fieldName) {
                    var originalFieldConfig = originalFieldConfigMap_3[fieldName];
                    if (testFn(fieldName, originalFieldConfig)) {
                        selectedFields[fieldName] = originalFieldConfig;
                    }
                });
            }
            return undefined;
        },
        _a));
    return selectedFields;
}
function modifyObjectFields(schema, typeName, testFn, newFields) {
    var _a;
    var removedFields = {};
    var newSchema = mapSchema(schema, (_a = {},
        _a[exports.MapperKind.OBJECT_TYPE] = function (type) {
            if (type.name === typeName) {
                var config = type.toConfig();
                var originalFieldConfigMap_4 = config.fields;
                var newFieldConfigMap_3 = {};
                Object.keys(originalFieldConfigMap_4).forEach(function (fieldName) {
                    var originalFieldConfig = originalFieldConfigMap_4[fieldName];
                    if (testFn(fieldName, originalFieldConfig)) {
                        removedFields[fieldName] = originalFieldConfig;
                    }
                    else {
                        newFieldConfigMap_3[fieldName] = originalFieldConfig;
                    }
                });
                Object.keys(newFields).forEach(function (fieldName) {
                    var fieldConfig = newFields[fieldName];
                    newFieldConfigMap_3[fieldName] = fieldConfig;
                });
                return correctASTNodes(new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, config), { fields: newFieldConfigMap_3 })));
            }
        },
        _a));
    return [newSchema, removedFields];
}

function renameType(type, newTypeName) {
    if (graphql.isObjectType(type)) {
        return new graphql.GraphQLObjectType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    else if (graphql.isInterfaceType(type)) {
        return new graphql.GraphQLInterfaceType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    else if (graphql.isUnionType(type)) {
        return new graphql.GraphQLUnionType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    else if (graphql.isInputObjectType(type)) {
        return new graphql.GraphQLInputObjectType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    else if (graphql.isEnumType(type)) {
        return new graphql.GraphQLEnumType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    else if (graphql.isScalarType(type)) {
        return new graphql.GraphQLScalarType(tslib.__assign(tslib.__assign({}, type.toConfig()), { name: newTypeName, astNode: type.astNode == null
                ? type.astNode
                : tslib.__assign(tslib.__assign({}, type.astNode), { name: tslib.__assign(tslib.__assign({}, type.astNode.name), { value: newTypeName }) }), extensionASTNodes: type.extensionASTNodes == null
                ? type.extensionASTNodes
                : type.extensionASTNodes.map(function (node) { return (tslib.__assign(tslib.__assign({}, node), { name: tslib.__assign(tslib.__assign({}, node.name), { value: newTypeName }) })); }) }));
    }
    throw new Error("Unknown type " + type + ".");
}

/**
 * Given a selectionSet, adds all of the fields in that selection to
 * the passed in map of fields, and returns it at the end.
 *
 * CollectFields requires the "runtime type" of an object. For a field which
 * returns an Interface or Union type, the "runtime type" will be the actual
 * Object type returned by that field.
 *
 * @internal
 */
function collectFields$1(exeContext, runtimeType, selectionSet, fields, visitedFragmentNames) {
    var e_1, _a;
    try {
        for (var _b = tslib.__values(selectionSet.selections), _c = _b.next(); !_c.done; _c = _b.next()) {
            var selection = _c.value;
            switch (selection.kind) {
                case graphql.Kind.FIELD: {
                    if (!shouldIncludeNode(exeContext, selection)) {
                        continue;
                    }
                    var name_1 = getFieldEntryKey(selection);
                    if (!(name_1 in fields)) {
                        fields[name_1] = [];
                    }
                    fields[name_1].push(selection);
                    break;
                }
                case graphql.Kind.INLINE_FRAGMENT: {
                    if (!shouldIncludeNode(exeContext, selection) ||
                        !doesFragmentConditionMatch(exeContext, selection, runtimeType)) {
                        continue;
                    }
                    collectFields$1(exeContext, runtimeType, selection.selectionSet, fields, visitedFragmentNames);
                    break;
                }
                case graphql.Kind.FRAGMENT_SPREAD: {
                    var fragName = selection.name.value;
                    if (visitedFragmentNames[fragName] || !shouldIncludeNode(exeContext, selection)) {
                        continue;
                    }
                    visitedFragmentNames[fragName] = true;
                    var fragment = exeContext.fragments[fragName];
                    if (!fragment || !doesFragmentConditionMatch(exeContext, fragment, runtimeType)) {
                        continue;
                    }
                    collectFields$1(exeContext, runtimeType, fragment.selectionSet, fields, visitedFragmentNames);
                    break;
                }
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
    return fields;
}
/**
 * Determines if a field should be included based on the @include and @skip
 * directives, where @skip has higher precedence than @include.
 */
function shouldIncludeNode(exeContext, node) {
    var skip = graphql.getDirectiveValues(graphql.GraphQLSkipDirective, node, exeContext.variableValues);
    if ((skip === null || skip === void 0 ? void 0 : skip.if) === true) {
        return false;
    }
    var include = graphql.getDirectiveValues(graphql.GraphQLIncludeDirective, node, exeContext.variableValues);
    if ((include === null || include === void 0 ? void 0 : include.if) === false) {
        return false;
    }
    return true;
}
/**
 * Determines if a fragment is applicable to the given type.
 */
function doesFragmentConditionMatch(exeContext, fragment, type) {
    var typeConditionNode = fragment.typeCondition;
    if (!typeConditionNode) {
        return true;
    }
    var conditionalType = graphql.typeFromAST(exeContext.schema, typeConditionNode);
    if (conditionalType === type) {
        return true;
    }
    if (graphql.isAbstractType(conditionalType)) {
        return exeContext.schema.isPossibleType(conditionalType, type);
    }
    return false;
}
/**
 * Implements the logic to compute the key of a given field's entry
 */
function getFieldEntryKey(node) {
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    return node.alias ? node.alias.value : node.name.value;
}

/**
 * Given an AsyncIterable and a callback function, return an AsyncIterator
 * which produces values mapped via calling the callback function.
 */
function mapAsyncIterator(iterator, callback, rejectCallback) {
    var _a;
    var $return;
    var abruptClose;
    if (typeof iterator.return === 'function') {
        $return = iterator.return;
        abruptClose = function (error) {
            var rethrow = function () { return Promise.reject(error); };
            return $return.call(iterator).then(rethrow, rethrow);
        };
    }
    function mapResult(result) {
        return result.done ? result : asyncMapValue(result.value, callback).then(iteratorResult, abruptClose);
    }
    var mapReject;
    if (rejectCallback) {
        // Capture rejectCallback to ensure it cannot be null.
        var reject_1 = rejectCallback;
        mapReject = function (error) { return asyncMapValue(error, reject_1).then(iteratorResult, abruptClose); };
    }
    return _a = {
            next: function () {
                return iterator.next().then(mapResult, mapReject);
            },
            return: function () {
                return $return
                    ? $return.call(iterator).then(mapResult, mapReject)
                    : Promise.resolve({ value: undefined, done: true });
            },
            throw: function (error) {
                if (typeof iterator.throw === 'function') {
                    return iterator.throw(error).then(mapResult, mapReject);
                }
                return Promise.reject(error).catch(abruptClose);
            }
        },
        _a[Symbol.asyncIterator] = function () {
            return this;
        },
        _a;
}
function asyncMapValue(value, callback) {
    return new Promise(function (resolve) { return resolve(callback(value)); });
}
function iteratorResult(value) {
    return { value: value, done: false };
}

function astFromType(type) {
    if (graphql.isNonNullType(type)) {
        var innerType = astFromType(type.ofType);
        if (innerType.kind === graphql.Kind.NON_NULL_TYPE) {
            throw new Error("Invalid type node " + JSON.stringify(type) + ". Inner type of non-null type cannot be a non-null type.");
        }
        return {
            kind: graphql.Kind.NON_NULL_TYPE,
            type: innerType,
        };
    }
    else if (graphql.isListType(type)) {
        return {
            kind: graphql.Kind.LIST_TYPE,
            type: astFromType(type.ofType),
        };
    }
    return {
        kind: graphql.Kind.NAMED_TYPE,
        name: {
            kind: graphql.Kind.NAME,
            value: type.name,
        },
    };
}

function updateArgument(argName, argType, argumentNodes, variableDefinitionsMap, variableValues, newArg) {
    var varName;
    var numGeneratedVariables = 0;
    do {
        varName = "_v" + (numGeneratedVariables++).toString() + "_" + argName;
    } while (varName in variableDefinitionsMap);
    argumentNodes[argName] = {
        kind: graphql.Kind.ARGUMENT,
        name: {
            kind: graphql.Kind.NAME,
            value: argName,
        },
        value: {
            kind: graphql.Kind.VARIABLE,
            name: {
                kind: graphql.Kind.NAME,
                value: varName,
            },
        },
    };
    variableDefinitionsMap[varName] = {
        kind: graphql.Kind.VARIABLE_DEFINITION,
        variable: {
            kind: graphql.Kind.VARIABLE,
            name: {
                kind: graphql.Kind.NAME,
                value: varName,
            },
        },
        type: astFromType(argType),
    };
    if (newArg === undefined) {
        delete variableValues[varName];
    }
    else {
        variableValues[varName] = newArg;
    }
}

function implementsAbstractType(schema, typeA, typeB) {
    if (typeA === typeB) {
        return true;
    }
    else if (graphql.isCompositeType(typeA) && graphql.isCompositeType(typeB)) {
        return graphql.doTypesOverlap(schema, typeA, typeB);
    }
    return false;
}

var ERROR_SYMBOL = Symbol('subschemaErrors');
function relocatedError(originalError, path) {
    return new graphql.GraphQLError(originalError.message, originalError.nodes, originalError.source, originalError.positions, path === null ? undefined : path === undefined ? originalError.path : path, originalError.originalError, originalError.extensions);
}
function slicedError(originalError) {
    return relocatedError(originalError, originalError.path != null ? originalError.path.slice(1) : undefined);
}
function getErrorsByPathSegment(errors) {
    var record = Object.create(null);
    errors.forEach(function (error) {
        if (!error.path || error.path.length < 2) {
            return;
        }
        var pathSegment = error.path[1];
        var current = pathSegment in record ? record[pathSegment] : [];
        current.push(slicedError(error));
        record[pathSegment] = current;
    });
    return record;
}
function setErrors(result, errors) {
    result[ERROR_SYMBOL] = errors;
}
function getErrors(result, pathSegment) {
    var e_1, _a;
    var errors = result != null ? result[ERROR_SYMBOL] : result;
    if (!Array.isArray(errors)) {
        return null;
    }
    var fieldErrors = [];
    try {
        for (var errors_1 = tslib.__values(errors), errors_1_1 = errors_1.next(); !errors_1_1.done; errors_1_1 = errors_1.next()) {
            var error = errors_1_1.value;
            if (!error.path || error.path[0] === pathSegment) {
                fieldErrors.push(error);
            }
        }
    }
    catch (e_1_1) { e_1 = { error: e_1_1 }; }
    finally {
        try {
            if (errors_1_1 && !errors_1_1.done && (_a = errors_1.return)) _a.call(errors_1);
        }
        finally { if (e_1) throw e_1.error; }
    }
    return fieldErrors;
}

function inputFieldToFieldConfig(field) {
    return {
        description: field.description,
        type: field.type,
        defaultValue: field.defaultValue,
        extensions: field.extensions,
        astNode: field.astNode,
    };
}
function fieldToFieldConfig(field) {
    return {
        description: field.description,
        type: field.type,
        args: argsToFieldConfigArgumentMap(field.args),
        resolve: field.resolve,
        subscribe: field.subscribe,
        deprecationReason: field.deprecationReason,
        extensions: field.extensions,
        astNode: field.astNode,
    };
}
function argsToFieldConfigArgumentMap(args) {
    var newArguments = {};
    args.forEach(function (arg) {
        newArguments[arg.name] = argumentToArgumentConfig(arg);
    });
    return newArguments;
}
function argumentToArgumentConfig(arg) {
    return {
        description: arg.description,
        type: arg.type,
        defaultValue: arg.defaultValue,
        extensions: arg.extensions,
        astNode: arg.astNode,
    };
}

function observableToAsyncIterable(observable) {
    var _a;
    var pullQueue = [];
    var pushQueue = [];
    var listening = true;
    var pushValue = function (value) {
        if (pullQueue.length !== 0) {
            pullQueue.shift()({ value: value, done: false });
        }
        else {
            pushQueue.push({ value: value });
        }
    };
    var pushError = function (error) {
        if (pullQueue.length !== 0) {
            pullQueue.shift()({ value: { errors: [error] }, done: false });
        }
        else {
            pushQueue.push({ value: { errors: [error] } });
        }
    };
    var pullValue = function () {
        return new Promise(function (resolve) {
            if (pushQueue.length !== 0) {
                var element = pushQueue.shift();
                // either {value: {errors: [...]}} or {value: ...}
                resolve(tslib.__assign(tslib.__assign({}, element), { done: false }));
            }
            else {
                pullQueue.push(resolve);
            }
        });
    };
    var subscription = observable.subscribe({
        next: function (value) {
            pushValue(value);
        },
        error: function (err) {
            pushError(err);
        },
    });
    var emptyQueue = function () {
        if (listening) {
            listening = false;
            subscription.unsubscribe();
            pullQueue.forEach(function (resolve) { return resolve({ value: undefined, done: true }); });
            pullQueue.length = 0;
            pushQueue.length = 0;
        }
    };
    return _a = {
            next: function () {
                return listening ? pullValue() : this.return();
            },
            return: function () {
                emptyQueue();
                return Promise.resolve({ value: undefined, done: true });
            },
            throw: function (error) {
                emptyQueue();
                return Promise.reject(error);
            }
        },
        _a[Symbol.asyncIterator] = function () {
            return this;
        },
        _a;
}

function visitData(data, enter, leave) {
    if (Array.isArray(data)) {
        return data.map(function (value) { return visitData(value, enter, leave); });
    }
    else if (typeof data === 'object') {
        var newData_1 = enter != null ? enter(data) : data;
        if (newData_1 != null) {
            Object.keys(newData_1).forEach(function (key) {
                var value = newData_1[key];
                newData_1[key] = visitData(value, enter, leave);
            });
        }
        return leave != null ? leave(newData_1) : newData_1;
    }
    return data;
}
function visitErrors(errors, visitor) {
    return errors.map(function (error) { return visitor(error); });
}
function visitResult(result, request, schema, resultVisitorMap, errorVisitorMap) {
    var partialExecutionContext = {
        schema: schema,
        fragments: request.document.definitions.reduce(function (acc, def) {
            if (def.kind === graphql.Kind.FRAGMENT_DEFINITION) {
                acc[def.name.value] = def;
            }
            return acc;
        }, {}),
        variableValues: request.variables,
    };
    var errorInfo = {
        segmentInfoMap: new Map(),
        unpathedErrors: [],
    };
    var data = result.data;
    var errors = result.errors;
    var visitingErrors = errors != null && errorVisitorMap != null;
    if (data != null) {
        result.data = visitRoot(data, graphql.getOperationAST(request.document, undefined), partialExecutionContext, resultVisitorMap, visitingErrors ? errors : undefined, errorInfo);
    }
    if (visitingErrors) {
        result.errors = visitErrorsByType(errors, errorVisitorMap, errorInfo);
    }
    return result;
}
function visitErrorsByType(errors, errorVisitorMap, errorInfo) {
    return errors.map(function (error) {
        var pathSegmentsInfo = errorInfo.segmentInfoMap.get(error);
        if (pathSegmentsInfo == null) {
            return error;
        }
        return pathSegmentsInfo.reduceRight(function (acc, segmentInfo) {
            var typeName = segmentInfo.type.name;
            var typeVisitorMap = errorVisitorMap[typeName];
            if (typeVisitorMap == null) {
                return acc;
            }
            var errorVisitor = typeVisitorMap[segmentInfo.fieldName];
            return errorVisitor == null ? acc : errorVisitor(acc, segmentInfo.pathIndex);
        }, error);
    });
}
function visitRoot(root, operation, exeContext, resultVisitorMap, errors, errorInfo) {
    var operationRootType = graphql.getOperationRootType(exeContext.schema, operation);
    var collectedFields = collectFields$1(exeContext, operationRootType, operation.selectionSet, Object.create(null), Object.create(null));
    return visitObjectValue(root, operationRootType, collectedFields, exeContext, resultVisitorMap, 0, errors, errorInfo);
}
function visitObjectValue(object, type, fieldNodeMap, exeContext, resultVisitorMap, pathIndex, errors, errorInfo) {
    var fieldMap = type.getFields();
    var typeVisitorMap = resultVisitorMap === null || resultVisitorMap === void 0 ? void 0 : resultVisitorMap[type.name];
    var enterObject = typeVisitorMap === null || typeVisitorMap === void 0 ? void 0 : typeVisitorMap.__enter;
    var newObject = enterObject != null ? enterObject(object) : object;
    var sortedErrors;
    var errorMap;
    if (errors != null) {
        sortedErrors = sortErrorsByPathSegment(errors, pathIndex);
        errorMap = sortedErrors.errorMap;
        errorInfo.unpathedErrors = errorInfo.unpathedErrors.concat(sortedErrors.unpathedErrors);
    }
    Object.keys(fieldNodeMap).forEach(function (responseKey) {
        var subFieldNodes = fieldNodeMap[responseKey];
        var fieldName = subFieldNodes[0].name.value;
        var fieldType = fieldMap[fieldName].type;
        var newPathIndex = pathIndex + 1;
        var fieldErrors;
        if (errors != null) {
            fieldErrors = errorMap[responseKey];
            if (fieldErrors != null) {
                delete errorMap[responseKey];
            }
            addPathSegmentInfo(type, fieldName, newPathIndex, fieldErrors, errorInfo);
        }
        var newValue = visitFieldValue(object[responseKey], fieldType, subFieldNodes, exeContext, resultVisitorMap, newPathIndex, fieldErrors, errorInfo);
        updateObject(newObject, responseKey, newValue, typeVisitorMap, fieldName);
    });
    var oldTypename = newObject.__typename;
    if (oldTypename != null) {
        updateObject(newObject, '__typename', oldTypename, typeVisitorMap, '__typename');
    }
    if (errors != null) {
        Object.keys(errorMap).forEach(function (unknownResponseKey) {
            errorInfo.unpathedErrors = errorInfo.unpathedErrors.concat(errorMap[unknownResponseKey]);
        });
    }
    var leaveObject = typeVisitorMap === null || typeVisitorMap === void 0 ? void 0 : typeVisitorMap.__leave;
    return leaveObject != null ? leaveObject(newObject) : newObject;
}
function updateObject(object, responseKey, newValue, typeVisitorMap, fieldName) {
    if (typeVisitorMap == null) {
        object[responseKey] = newValue;
        return;
    }
    var fieldVisitor = typeVisitorMap[fieldName];
    if (fieldVisitor == null) {
        object[responseKey] = newValue;
        return;
    }
    var visitedValue = fieldVisitor(newValue);
    if (visitedValue === undefined) {
        delete object[responseKey];
        return;
    }
    object[responseKey] = visitedValue;
}
function visitListValue(list, returnType, fieldNodes, exeContext, resultVisitorMap, pathIndex, errors, errorInfo) {
    return list.map(function (listMember) {
        return visitFieldValue(listMember, returnType, fieldNodes, exeContext, resultVisitorMap, pathIndex + 1, errors, errorInfo);
    });
}
function visitFieldValue(value, returnType, fieldNodes, exeContext, resultVisitorMap, pathIndex, errors, errorInfo) {
    if (errors === void 0) { errors = []; }
    if (value == null) {
        return value;
    }
    var nullableType = graphql.getNullableType(returnType);
    if (graphql.isListType(nullableType)) {
        return visitListValue(value, nullableType.ofType, fieldNodes, exeContext, resultVisitorMap, pathIndex, errors, errorInfo);
    }
    else if (graphql.isAbstractType(nullableType)) {
        var finalType = exeContext.schema.getType(value.__typename);
        var collectedFields = collectSubFields(exeContext, finalType, fieldNodes);
        return visitObjectValue(value, finalType, collectedFields, exeContext, resultVisitorMap, pathIndex, errors, errorInfo);
    }
    else if (graphql.isObjectType(nullableType)) {
        var collectedFields = collectSubFields(exeContext, nullableType, fieldNodes);
        return visitObjectValue(value, nullableType, collectedFields, exeContext, resultVisitorMap, pathIndex, errors, errorInfo);
    }
    var typeVisitorMap = resultVisitorMap === null || resultVisitorMap === void 0 ? void 0 : resultVisitorMap[nullableType.name];
    if (typeVisitorMap == null) {
        return value;
    }
    var visitedValue = typeVisitorMap(value);
    return visitedValue === undefined ? value : visitedValue;
}
function sortErrorsByPathSegment(errors, pathIndex) {
    var errorMap = Object.create(null);
    var unpathedErrors = [];
    errors.forEach(function (error) {
        var _a;
        var pathSegment = (_a = error.path) === null || _a === void 0 ? void 0 : _a[pathIndex];
        if (pathSegment == null) {
            unpathedErrors.push(error);
            return;
        }
        if (pathSegment in errorMap) {
            errorMap[pathSegment].push(error);
        }
        else {
            errorMap[pathSegment] = [error];
        }
    });
    return {
        errorMap: errorMap,
        unpathedErrors: unpathedErrors,
    };
}
function addPathSegmentInfo(type, fieldName, pathIndex, errors, errorInfo) {
    if (errors === void 0) { errors = []; }
    errors.forEach(function (error) {
        var segmentInfo = {
            type: type,
            fieldName: fieldName,
            pathIndex: pathIndex,
        };
        var pathSegmentsInfo = errorInfo.segmentInfoMap.get(error);
        if (pathSegmentsInfo == null) {
            errorInfo.segmentInfoMap.set(error, [segmentInfo]);
        }
        else {
            pathSegmentsInfo.push(segmentInfo);
        }
    });
}
function collectSubFields(exeContext, type, fieldNodes) {
    var subFieldNodes = Object.create(null);
    var visitedFragmentNames = Object.create(null);
    fieldNodes.forEach(function (fieldNode) {
        subFieldNodes = collectFields$1(exeContext, type, fieldNode.selectionSet, subFieldNodes, visitedFragmentNames);
    });
    return subFieldNodes;
}

function valueMatchesCriteria(value, criteria) {
    if (value == null) {
        return value === criteria;
    }
    else if (Array.isArray(value)) {
        return Array.isArray(criteria) && value.every(function (val, index) { return valueMatchesCriteria(val, criteria[index]); });
    }
    else if (typeof value === 'object') {
        return (typeof criteria === 'object' &&
            criteria &&
            Object.keys(criteria).every(function (propertyName) { return valueMatchesCriteria(value[propertyName], criteria[propertyName]); }));
    }
    else if (criteria instanceof RegExp) {
        return criteria.test(value);
    }
    return value === criteria;
}

exports.ERROR_SYMBOL = ERROR_SYMBOL;
exports.SchemaDirectiveVisitor = SchemaDirectiveVisitor;
exports.SchemaVisitor = SchemaVisitor;
exports.addTypes = addTypes;
exports.appendObjectFields = appendObjectFields;
exports.applyRequestTransforms = applyRequestTransforms;
exports.applyResultTransforms = applyResultTransforms;
exports.applySchemaTransforms = applySchemaTransforms;
exports.argsToFieldConfigArgumentMap = argsToFieldConfigArgumentMap;
exports.argumentToArgumentConfig = argumentToArgumentConfig;
exports.asArray = asArray;
exports.buildOperationNodeForField = buildOperationNodeForField;
exports.checkValidationErrors = checkValidationErrors;
exports.cloneDirective = cloneDirective;
exports.cloneSchema = cloneSchema;
exports.cloneType = cloneType;
exports.collectFields = collectFields$1;
exports.compareNodes = compareNodes;
exports.compareStrings = compareStrings;
exports.concatInlineFragments = concatInlineFragments;
exports.correctASTNodes = correctASTNodes;
exports.createNamedStub = createNamedStub;
exports.createSchemaDefinition = createSchemaDefinition;
exports.createStub = createStub;
exports.debugLog = debugLog;
exports.fieldToFieldConfig = fieldToFieldConfig;
exports.filterSchema = filterSchema;
exports.fixSchemaAst = fixSchemaAst;
exports.fixWindowsPath = fixWindowsPath;
exports.flattenArray = flattenArray;
exports.forEachDefaultValue = forEachDefaultValue;
exports.forEachField = forEachField;
exports.getArgumentValues = getArgumentValues;
exports.getBuiltInForStub = getBuiltInForStub;
exports.getDirectives = getDirectives;
exports.getErrors = getErrors;
exports.getErrorsByPathSegment = getErrorsByPathSegment;
exports.getFieldsWithDirectives = getFieldsWithDirectives;
exports.getImplementingTypes = getImplementingTypes;
exports.getLeadingCommentBlock = getLeadingCommentBlock;
exports.getResolversFromSchema = getResolversFromSchema;
exports.getResponseKeyFromInfo = getResponseKeyFromInfo;
exports.getUserTypesFromSchema = getUserTypesFromSchema;
exports.healSchema = healSchema;
exports.healTypes = healTypes;
exports.hoistFieldNodes = hoistFieldNodes;
exports.implementsAbstractType = implementsAbstractType;
exports.inputFieldToFieldConfig = inputFieldToFieldConfig;
exports.isDescribable = isDescribable;
exports.isDocumentString = isDocumentString;
exports.isEqual = isEqual;
exports.isNamedStub = isNamedStub;
exports.isNotEqual = isNotEqual;
exports.isValidPath = isValidPath;
exports.mapAsyncIterator = mapAsyncIterator;
exports.mapSchema = mapSchema;
exports.mergeDeep = mergeDeep;
exports.modifyObjectFields = modifyObjectFields;
exports.nodeToString = nodeToString;
exports.observableToAsyncIterable = observableToAsyncIterable;
exports.parseFragmentToInlineFragment = parseFragmentToInlineFragment;
exports.parseGraphQLJSON = parseGraphQLJSON;
exports.parseGraphQLSDL = parseGraphQLSDL;
exports.parseInputValue = parseInputValue;
exports.parseInputValueLiteral = parseInputValueLiteral;
exports.parseSelectionSet = parseSelectionSet;
exports.preAliasFieldNode = preAliasFieldNode;
exports.printSchemaWithDirectives = printSchemaWithDirectives;
exports.pruneSchema = pruneSchema;
exports.relocatedError = relocatedError;
exports.removeObjectFields = removeObjectFields;
exports.renameFieldNode = renameFieldNode;
exports.renameType = renameType;
exports.rewireTypes = rewireTypes;
exports.selectObjectFields = selectObjectFields;
exports.serializeInputValue = serializeInputValue;
exports.setErrors = setErrors;
exports.slicedError = slicedError;
exports.transformCommentsToDescriptions = transformCommentsToDescriptions;
exports.transformInputValue = transformInputValue;
exports.typeContainsSelectionSet = typeContainsSelectionSet;
exports.typesContainSelectionSet = typesContainSelectionSet;
exports.updateArgument = updateArgument;
exports.validateGraphQlDocuments = validateGraphQlDocuments;
exports.valueMatchesCriteria = valueMatchesCriteria;
exports.visitData = visitData;
exports.visitErrors = visitErrors;
exports.visitResult = visitResult;
exports.visitSchema = visitSchema;
exports.wrapFieldNode = wrapFieldNode;
//# sourceMappingURL=index.cjs.js.map
