"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const experimental_utils_1 = require("@typescript-eslint/experimental-utils");
const util = __importStar(require("../util"));
// #region Options Type Config
var PredefinedFormats;
(function (PredefinedFormats) {
    PredefinedFormats[PredefinedFormats["camelCase"] = 1] = "camelCase";
    PredefinedFormats[PredefinedFormats["strictCamelCase"] = 2] = "strictCamelCase";
    PredefinedFormats[PredefinedFormats["PascalCase"] = 4] = "PascalCase";
    PredefinedFormats[PredefinedFormats["StrictPascalCase"] = 8] = "StrictPascalCase";
    // eslint-disable-next-line @typescript-eslint/camelcase
    PredefinedFormats[PredefinedFormats["snake_case"] = 16] = "snake_case";
    PredefinedFormats[PredefinedFormats["UPPER_CASE"] = 32] = "UPPER_CASE";
})(PredefinedFormats || (PredefinedFormats = {}));
var UnderscoreOptions;
(function (UnderscoreOptions) {
    UnderscoreOptions[UnderscoreOptions["forbid"] = 1] = "forbid";
    UnderscoreOptions[UnderscoreOptions["allow"] = 2] = "allow";
    UnderscoreOptions[UnderscoreOptions["require"] = 4] = "require";
})(UnderscoreOptions || (UnderscoreOptions = {}));
var Selectors;
(function (Selectors) {
    // variableLike
    Selectors[Selectors["variable"] = 1] = "variable";
    Selectors[Selectors["function"] = 2] = "function";
    Selectors[Selectors["parameter"] = 4] = "parameter";
    // memberLike
    Selectors[Selectors["property"] = 8] = "property";
    Selectors[Selectors["parameterProperty"] = 16] = "parameterProperty";
    Selectors[Selectors["method"] = 32] = "method";
    Selectors[Selectors["accessor"] = 64] = "accessor";
    Selectors[Selectors["enumMember"] = 128] = "enumMember";
    // typeLike
    Selectors[Selectors["class"] = 256] = "class";
    Selectors[Selectors["interface"] = 512] = "interface";
    Selectors[Selectors["typeAlias"] = 1024] = "typeAlias";
    Selectors[Selectors["enum"] = 2048] = "enum";
    Selectors[Selectors["typeParameter"] = 4096] = "typeParameter";
})(Selectors || (Selectors = {}));
const SELECTOR_COUNT = util.getEnumNames(Selectors).length;
var MetaSelectors;
(function (MetaSelectors) {
    MetaSelectors[MetaSelectors["default"] = -1] = "default";
    MetaSelectors[MetaSelectors["variableLike"] = 7] = "variableLike";
    MetaSelectors[MetaSelectors["memberLike"] = 248] = "memberLike";
    MetaSelectors[MetaSelectors["typeLike"] = 7936] = "typeLike";
})(MetaSelectors || (MetaSelectors = {}));
var Modifiers;
(function (Modifiers) {
    Modifiers[Modifiers["readonly"] = 1] = "readonly";
    Modifiers[Modifiers["static"] = 2] = "static";
    Modifiers[Modifiers["public"] = 4] = "public";
    Modifiers[Modifiers["protected"] = 8] = "protected";
    Modifiers[Modifiers["private"] = 16] = "private";
    Modifiers[Modifiers["abstract"] = 32] = "abstract";
})(Modifiers || (Modifiers = {}));
var TypeModifiers;
(function (TypeModifiers) {
    TypeModifiers[TypeModifiers["boolean"] = 1024] = "boolean";
    TypeModifiers[TypeModifiers["string"] = 2048] = "string";
    TypeModifiers[TypeModifiers["number"] = 4096] = "number";
    TypeModifiers[TypeModifiers["function"] = 8192] = "function";
    TypeModifiers[TypeModifiers["array"] = 16384] = "array";
})(TypeModifiers || (TypeModifiers = {}));
// #endregion Options Type Config
// #region Schema Config
const UNDERSCORE_SCHEMA = {
    type: 'string',
    enum: util.getEnumNames(UnderscoreOptions),
};
const PREFIX_SUFFIX_SCHEMA = {
    type: 'array',
    items: {
        type: 'string',
        minLength: 1,
    },
    additionalItems: false,
};
const MATCH_REGEX_SCHEMA = {
    type: 'object',
    properties: {
        match: { type: 'boolean' },
        regex: { type: 'string' },
    },
    required: ['match', 'regex'],
};
const FORMAT_OPTIONS_PROPERTIES = {
    format: {
        oneOf: [
            {
                type: 'array',
                items: {
                    type: 'string',
                    enum: util.getEnumNames(PredefinedFormats),
                },
                additionalItems: false,
            },
            {
                type: 'null',
            },
        ],
    },
    custom: MATCH_REGEX_SCHEMA,
    leadingUnderscore: UNDERSCORE_SCHEMA,
    trailingUnderscore: UNDERSCORE_SCHEMA,
    prefix: PREFIX_SUFFIX_SCHEMA,
    suffix: PREFIX_SUFFIX_SCHEMA,
};
function selectorSchema(selectorString, allowType, modifiers) {
    const selector = {
        filter: {
            oneOf: [
                {
                    type: 'string',
                    minLength: 1,
                },
                MATCH_REGEX_SCHEMA,
            ],
        },
        selector: {
            type: 'string',
            enum: [selectorString],
        },
    };
    if (modifiers && modifiers.length > 0) {
        selector.modifiers = {
            type: 'array',
            items: {
                type: 'string',
                enum: modifiers,
            },
            additionalItems: false,
        };
    }
    if (allowType) {
        selector.types = {
            type: 'array',
            items: {
                type: 'string',
                enum: util.getEnumNames(TypeModifiers),
            },
            additionalItems: false,
        };
    }
    return [
        {
            type: 'object',
            properties: Object.assign(Object.assign({}, FORMAT_OPTIONS_PROPERTIES), selector),
            required: ['selector', 'format'],
            additionalProperties: false,
        },
    ];
}
const SCHEMA = {
    type: 'array',
    items: {
        oneOf: [
            ...selectorSchema('default', false, util.getEnumNames(Modifiers)),
            ...selectorSchema('variableLike', false),
            ...selectorSchema('variable', true),
            ...selectorSchema('function', false),
            ...selectorSchema('parameter', true),
            ...selectorSchema('memberLike', false, [
                'private',
                'protected',
                'public',
                'static',
                'readonly',
                'abstract',
            ]),
            ...selectorSchema('property', true, [
                'private',
                'protected',
                'public',
                'static',
                'readonly',
                'abstract',
            ]),
            ...selectorSchema('parameterProperty', true, [
                'private',
                'protected',
                'public',
                'readonly',
            ]),
            ...selectorSchema('method', false, [
                'private',
                'protected',
                'public',
                'static',
                'abstract',
            ]),
            ...selectorSchema('accessor', true, [
                'private',
                'protected',
                'public',
                'static',
                'abstract',
            ]),
            ...selectorSchema('enumMember', false),
            ...selectorSchema('typeLike', false, ['abstract']),
            ...selectorSchema('class', false, ['abstract']),
            ...selectorSchema('interface', false),
            ...selectorSchema('typeAlias', false),
            ...selectorSchema('enum', false),
            ...selectorSchema('typeParameter', false),
        ],
    },
    additionalItems: false,
};
// #endregion Schema Config
// This essentially mirrors ESLint's `camelcase` rule
// note that that rule ignores leading and trailing underscores and only checks those in the middle of a variable name
const defaultCamelCaseAllTheThingsConfig = [
    {
        selector: 'default',
        format: ['camelCase'],
        leadingUnderscore: 'allow',
        trailingUnderscore: 'allow',
    },
    {
        selector: 'variable',
        format: ['camelCase', 'UPPER_CASE'],
        leadingUnderscore: 'allow',
        trailingUnderscore: 'allow',
    },
    {
        selector: 'typeLike',
        format: ['PascalCase'],
    },
];
exports.default = util.createRule({
    name: 'naming-convention',
    meta: {
        docs: {
            category: 'Variables',
            description: 'Enforces naming conventions for everything across a codebase',
            recommended: false,
            // technically only requires type checking if the user uses "type" modifiers
            requiresTypeChecking: true,
        },
        type: 'suggestion',
        messages: {
            unexpectedUnderscore: '{{type}} name {{name}} must not have a {{position}} underscore.',
            missingUnderscore: '{{type}} name {{name}} must have a {{position}} underscore.',
            missingAffix: '{{type}} name {{name}} must have one of the following {{position}}es: {{affixes}}',
            satisfyCustom: '{{type}} name {{name}} must {{regexMatch}} the RegExp: {{regex}}',
            doesNotMatchFormat: '{{type}} name {{name}} must match one of the following formats: {{formats}}',
        },
        schema: SCHEMA,
    },
    defaultOptions: defaultCamelCaseAllTheThingsConfig,
    create(contextWithoutDefaults) {
        const context = contextWithoutDefaults.options
            ? contextWithoutDefaults
            : // only apply the defaults when the user provides no config
                Object.setPrototypeOf({
                    options: defaultCamelCaseAllTheThingsConfig,
                }, contextWithoutDefaults);
        const validators = parseOptions(context);
        function handleMember(validator, node, modifiers) {
            if (!validator) {
                return;
            }
            const key = node.key;
            validator(key, modifiers);
        }
        function getMemberModifiers(node) {
            const modifiers = new Set();
            if (node.accessibility) {
                modifiers.add(Modifiers[node.accessibility]);
            }
            else {
                modifiers.add(Modifiers.public);
            }
            if (node.static) {
                modifiers.add(Modifiers.static);
            }
            if ('readonly' in node && node.readonly) {
                modifiers.add(Modifiers.readonly);
            }
            if (node.type === experimental_utils_1.AST_NODE_TYPES.TSAbstractClassProperty ||
                node.type === experimental_utils_1.AST_NODE_TYPES.TSAbstractMethodDefinition) {
                modifiers.add(Modifiers.abstract);
            }
            return modifiers;
        }
        return {
            // #region variable
            VariableDeclarator(node) {
                const validator = validators.variable;
                if (!validator) {
                    return;
                }
                const identifiers = [];
                getIdentifiersFromPattern(node.id, identifiers);
                identifiers.forEach(i => {
                    validator(i);
                });
            },
            // #endregion
            // #region function
            'FunctionDeclaration, TSDeclareFunction, FunctionExpression'(node) {
                const validator = validators.function;
                if (!validator || node.id === null) {
                    return;
                }
                validator(node.id);
            },
            // #endregion function
            // #region parameter
            'FunctionDeclaration, TSDeclareFunction, FunctionExpression, ArrowFunctionExpression'(node) {
                const validator = validators.parameter;
                if (!validator) {
                    return;
                }
                node.params.forEach(param => {
                    if (param.type === experimental_utils_1.AST_NODE_TYPES.TSParameterProperty) {
                        return;
                    }
                    const identifiers = [];
                    getIdentifiersFromPattern(param, identifiers);
                    identifiers.forEach(i => {
                        validator(i);
                    });
                });
            },
            // #endregion parameter
            // #region parameterProperty
            TSParameterProperty(node) {
                const validator = validators.parameterProperty;
                if (!validator) {
                    return;
                }
                const modifiers = getMemberModifiers(node);
                const identifiers = [];
                getIdentifiersFromPattern(node.parameter, identifiers);
                identifiers.forEach(i => {
                    validator(i, modifiers);
                });
            },
            // #endregion parameterProperty
            // #region property
            'Property[computed = false][kind = "init"][value.type != "ArrowFunctionExpression"][value.type != "FunctionExpression"][value.type != "TSEmptyBodyFunctionExpression"]'(node) {
                const modifiers = new Set([Modifiers.public]);
                handleMember(validators.property, node, modifiers);
            },
            ':matches(ClassProperty, TSAbstractClassProperty)[computed = false][value.type != "ArrowFunctionExpression"][value.type != "FunctionExpression"][value.type != "TSEmptyBodyFunctionExpression"]'(node) {
                const modifiers = getMemberModifiers(node);
                handleMember(validators.property, node, modifiers);
            },
            'TSPropertySignature[computed = false]'(node) {
                const modifiers = new Set([Modifiers.public]);
                if (node.readonly) {
                    modifiers.add(Modifiers.readonly);
                }
                handleMember(validators.property, node, modifiers);
            },
            // #endregion property
            // #region method
            [[
                'Property[computed = false][kind = "init"][value.type = "ArrowFunctionExpression"]',
                'Property[computed = false][kind = "init"][value.type = "FunctionExpression"]',
                'Property[computed = false][kind = "init"][value.type = "TSEmptyBodyFunctionExpression"]',
                'TSMethodSignature[computed = false]',
            ].join(', ')](node) {
                const modifiers = new Set([Modifiers.public]);
                handleMember(validators.method, node, modifiers);
            },
            [[
                ':matches(ClassProperty, TSAbstractClassProperty)[computed = false][value.type = "ArrowFunctionExpression"]',
                ':matches(ClassProperty, TSAbstractClassProperty)[computed = false][value.type = "FunctionExpression"]',
                ':matches(ClassProperty, TSAbstractClassProperty)[computed = false][value.type = "TSEmptyBodyFunctionExpression"]',
                ':matches(MethodDefinition, TSAbstractMethodDefinition)[computed = false][kind = "method"]',
            ].join(', ')](node) {
                const modifiers = getMemberModifiers(node);
                handleMember(validators.method, node, modifiers);
            },
            // #endregion method
            // #region accessor
            'Property[computed = false]:matches([kind = "get"], [kind = "set"])'(node) {
                const modifiers = new Set([Modifiers.public]);
                handleMember(validators.accessor, node, modifiers);
            },
            'MethodDefinition[computed = false]:matches([kind = "get"], [kind = "set"])'(node) {
                const modifiers = getMemberModifiers(node);
                handleMember(validators.accessor, node, modifiers);
            },
            // #endregion accessor
            // #region enumMember
            // computed is optional, so can't do [computed = false]
            'TSEnumMember[computed != true]'(node) {
                const validator = validators.enumMember;
                if (!validator) {
                    return;
                }
                const id = node.id;
                validator(id);
            },
            // #endregion enumMember
            // #region class
            'ClassDeclaration, ClassExpression'(node) {
                const validator = validators.class;
                if (!validator) {
                    return;
                }
                const id = node.id;
                if (id === null) {
                    return;
                }
                const modifiers = new Set();
                if (node.abstract) {
                    modifiers.add(Modifiers.abstract);
                }
                validator(id, modifiers);
            },
            // #endregion class
            // #region interface
            TSInterfaceDeclaration(node) {
                const validator = validators.interface;
                if (!validator) {
                    return;
                }
                validator(node.id);
            },
            // #endregion interface
            // #region typeAlias
            TSTypeAliasDeclaration(node) {
                const validator = validators.typeAlias;
                if (!validator) {
                    return;
                }
                validator(node.id);
            },
            // #endregion typeAlias
            // #region enum
            TSEnumDeclaration(node) {
                const validator = validators.enum;
                if (!validator) {
                    return;
                }
                validator(node.id);
            },
            // #endregion enum
            // #region typeParameter
            'TSTypeParameterDeclaration > TSTypeParameter'(node) {
                const validator = validators.typeParameter;
                if (!validator) {
                    return;
                }
                validator(node.name);
            },
        };
    },
});
function getIdentifiersFromPattern(pattern, identifiers) {
    switch (pattern.type) {
        case experimental_utils_1.AST_NODE_TYPES.Identifier:
            identifiers.push(pattern);
            break;
        case experimental_utils_1.AST_NODE_TYPES.ArrayPattern:
            pattern.elements.forEach(element => {
                if (element !== null) {
                    getIdentifiersFromPattern(element, identifiers);
                }
            });
            break;
        case experimental_utils_1.AST_NODE_TYPES.ObjectPattern:
            pattern.properties.forEach(property => {
                if (property.type === experimental_utils_1.AST_NODE_TYPES.RestElement) {
                    getIdentifiersFromPattern(property, identifiers);
                }
                else {
                    // this is a bit weird, but it's because ESTree doesn't have a new node type
                    // for object destructuring properties - it just reuses Property...
                    // https://github.com/estree/estree/blob/9ae284b71130d53226e7153b42f01bf819e6e657/es2015.md#L206-L211
                    // However, the parser guarantees this is safe (and there is error handling)
                    getIdentifiersFromPattern(property.value, identifiers);
                }
            });
            break;
        case experimental_utils_1.AST_NODE_TYPES.RestElement:
            getIdentifiersFromPattern(pattern.argument, identifiers);
            break;
        case experimental_utils_1.AST_NODE_TYPES.AssignmentPattern:
            getIdentifiersFromPattern(pattern.left, identifiers);
            break;
        case experimental_utils_1.AST_NODE_TYPES.MemberExpression:
            // ignore member expressions, as the everything must already be defined
            break;
        default:
            // https://github.com/typescript-eslint/typescript-eslint/issues/1282
            // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
            throw new Error(`Unexpected pattern type ${pattern.type}`);
    }
}
function parseOptions(context) {
    const normalizedOptions = context.options.map(opt => normalizeOption(opt));
    const parsedOptions = util.getEnumNames(Selectors).reduce((acc, k) => {
        acc[k] = createValidator(k, context, normalizedOptions);
        return acc;
    }, {});
    return parsedOptions;
}
function createValidator(type, context, allConfigs) {
    // make sure the "highest priority" configs are checked first
    const selectorType = Selectors[type];
    const configs = allConfigs
        // gather all of the applicable selectors
        .filter(c => (c.selector & selectorType) !== 0 ||
        c.selector === MetaSelectors.default)
        .sort((a, b) => {
        if (a.selector === b.selector) {
            // in the event of the same selector, order by modifier weight
            // sort descending - the type modifiers are "more important"
            return b.modifierWeight - a.modifierWeight;
        }
        /*
        meta selectors will always be larger numbers than the normal selectors they contain, as they are the sum of all
        of the selectors that they contain.
        to give normal selectors a higher priority, shift them all SELECTOR_COUNT bits to the left before comparison, so
        they are instead always guaranteed to be larger than the meta selectors.
        */
        const aSelector = isMetaSelector(a.selector)
            ? a.selector
            : a.selector << SELECTOR_COUNT;
        const bSelector = isMetaSelector(b.selector)
            ? b.selector
            : b.selector << SELECTOR_COUNT;
        // sort descending - the meta selectors are "least important"
        return bSelector - aSelector;
    });
    return (node, modifiers = new Set()) => {
        var _a, _b, _c;
        const originalName = node.type === experimental_utils_1.AST_NODE_TYPES.Identifier ? node.name : `${node.value}`;
        // return will break the loop and stop checking configs
        // it is only used when the name is known to have failed or succeeded a config.
        for (const config of configs) {
            if (((_a = config.filter) === null || _a === void 0 ? void 0 : _a.regex.test(originalName)) !== ((_b = config.filter) === null || _b === void 0 ? void 0 : _b.match)) {
                // name does not match the filter
                continue;
            }
            if ((_c = config.modifiers) === null || _c === void 0 ? void 0 : _c.some(modifier => !modifiers.has(modifier))) {
                // does not have the required modifiers
                continue;
            }
            if (!isCorrectType(node, config, context)) {
                // is not the correct type
                continue;
            }
            let name = originalName;
            name = validateUnderscore('leading', config, name, node, originalName);
            if (name === null) {
                // fail
                return;
            }
            name = validateUnderscore('trailing', config, name, node, originalName);
            if (name === null) {
                // fail
                return;
            }
            name = validateAffix('prefix', config, name, node, originalName);
            if (name === null) {
                // fail
                return;
            }
            name = validateAffix('suffix', config, name, node, originalName);
            if (name === null) {
                // fail
                return;
            }
            if (!validateCustom(config, name, node, originalName)) {
                // fail
                return;
            }
            if (!validatePredefinedFormat(config, name, node, originalName)) {
                // fail
                return;
            }
            // it's valid for this config, so we don't need to check any more configs
            return;
        }
    };
    // centralizes the logic for formatting the report data
    function formatReportData({ affixes, formats, originalName, position, custom, }) {
        var _a;
        return {
            type: selectorTypeToMessageString(type),
            name: originalName,
            position,
            affixes: affixes === null || affixes === void 0 ? void 0 : affixes.join(', '),
            formats: formats === null || formats === void 0 ? void 0 : formats.map(f => PredefinedFormats[f]).join(', '),
            regex: (_a = custom === null || custom === void 0 ? void 0 : custom.regex) === null || _a === void 0 ? void 0 : _a.toString(),
            regexMatch: (custom === null || custom === void 0 ? void 0 : custom.match) === true
                ? 'match'
                : (custom === null || custom === void 0 ? void 0 : custom.match) === false
                    ? 'not match'
                    : null,
        };
    }
    /**
     * @returns the name with the underscore removed, if it is valid according to the specified underscore option, null otherwise
     */
    function validateUnderscore(position, config, name, node, originalName) {
        const option = position === 'leading'
            ? config.leadingUnderscore
            : config.trailingUnderscore;
        if (!option) {
            return name;
        }
        const hasUnderscore = position === 'leading' ? name.startsWith('_') : name.endsWith('_');
        const trimUnderscore = position === 'leading'
            ? () => name.slice(1)
            : () => name.slice(0, -1);
        switch (option) {
            case UnderscoreOptions.allow:
                // no check - the user doesn't care if it's there or not
                break;
            case UnderscoreOptions.forbid:
                if (hasUnderscore) {
                    context.report({
                        node,
                        messageId: 'unexpectedUnderscore',
                        data: formatReportData({
                            originalName,
                            position,
                        }),
                    });
                    return null;
                }
                break;
            case UnderscoreOptions.require:
                if (!hasUnderscore) {
                    context.report({
                        node,
                        messageId: 'missingUnderscore',
                        data: formatReportData({
                            originalName,
                            position,
                        }),
                    });
                    return null;
                }
        }
        return hasUnderscore ? trimUnderscore() : name;
    }
    /**
     * @returns the name with the affix removed, if it is valid according to the specified affix option, null otherwise
     */
    function validateAffix(position, config, name, node, originalName) {
        const affixes = config[position];
        if (!affixes || affixes.length === 0) {
            return name;
        }
        for (const affix of affixes) {
            const hasAffix = position === 'prefix' ? name.startsWith(affix) : name.endsWith(affix);
            const trimAffix = position === 'prefix'
                ? () => name.slice(affix.length)
                : () => name.slice(0, -affix.length);
            if (hasAffix) {
                // matches, so trim it and return
                return trimAffix();
            }
        }
        context.report({
            node,
            messageId: 'missingAffix',
            data: formatReportData({
                originalName,
                position,
                affixes,
            }),
        });
        return null;
    }
    /**
     * @returns true if the name is valid according to the `regex` option, false otherwise
     */
    function validateCustom(config, name, node, originalName) {
        const custom = config.custom;
        if (!custom) {
            return true;
        }
        const result = custom.regex.test(name);
        if (custom.match && result) {
            return true;
        }
        if (!custom.match && !result) {
            return true;
        }
        context.report({
            node,
            messageId: 'satisfyCustom',
            data: formatReportData({
                originalName,
                custom,
            }),
        });
        return false;
    }
    /**
     * @returns true if the name is valid according to the `format` option, false otherwise
     */
    function validatePredefinedFormat(config, name, node, originalName) {
        const formats = config.format;
        if (formats === null || formats.length === 0) {
            return true;
        }
        for (const format of formats) {
            const checker = PredefinedFormatToCheckFunction[format];
            if (checker(name)) {
                return true;
            }
        }
        context.report({
            node,
            messageId: 'doesNotMatchFormat',
            data: formatReportData({
                originalName,
                formats,
            }),
        });
        return false;
    }
}
// #region Predefined Format Functions
/*
These format functions are taken from `tslint-consistent-codestyle/naming-convention`:
https://github.com/ajafff/tslint-consistent-codestyle/blob/ab156cc8881bcc401236d999f4ce034b59039e81/rules/namingConventionRule.ts#L603-L645

The licence for the code can be viewed here:
https://github.com/ajafff/tslint-consistent-codestyle/blob/ab156cc8881bcc401236d999f4ce034b59039e81/LICENSE
*/
/*
Why not regex here? Because it's actually really, really difficult to create a regex to handle
all of the unicode cases, and we have many non-english users that use non-english characters.
https://gist.github.com/mathiasbynens/6334847
*/
function isPascalCase(name) {
    return (name.length === 0 ||
        // eslint-disable-next-line @typescript-eslint/prefer-string-starts-ends-with
        (name[0] === name[0].toUpperCase() && !name.includes('_')));
}
function isStrictPascalCase(name) {
    return (name.length === 0 ||
        // eslint-disable-next-line @typescript-eslint/prefer-string-starts-ends-with
        (name[0] === name[0].toUpperCase() && hasStrictCamelHumps(name, true)));
}
function isCamelCase(name) {
    return (name.length === 0 ||
        // eslint-disable-next-line @typescript-eslint/prefer-string-starts-ends-with
        (name[0] === name[0].toLowerCase() && !name.includes('_')));
}
function isStrictCamelCase(name) {
    return (name.length === 0 ||
        // eslint-disable-next-line @typescript-eslint/prefer-string-starts-ends-with
        (name[0] === name[0].toLowerCase() && hasStrictCamelHumps(name, false)));
}
function hasStrictCamelHumps(name, isUpper) {
    function isUppercaseChar(char) {
        return char === char.toUpperCase() && char !== char.toLowerCase();
    }
    if (name.startsWith('_')) {
        return false;
    }
    for (let i = 1; i < name.length; ++i) {
        if (name[i] === '_') {
            return false;
        }
        if (isUpper === isUppercaseChar(name[i])) {
            if (isUpper) {
                return false;
            }
        }
        else {
            isUpper = !isUpper;
        }
    }
    return true;
}
function isSnakeCase(name) {
    return (name.length === 0 ||
        (name === name.toLowerCase() && validateUnderscores(name)));
}
function isUpperCase(name) {
    return (name.length === 0 ||
        (name === name.toUpperCase() && validateUnderscores(name)));
}
/** Check for leading trailing and adjacent underscores */
function validateUnderscores(name) {
    if (name.startsWith('_')) {
        return false;
    }
    let wasUnderscore = false;
    for (let i = 1; i < name.length; ++i) {
        if (name[i] === '_') {
            if (wasUnderscore) {
                return false;
            }
            wasUnderscore = true;
        }
        else {
            wasUnderscore = false;
        }
    }
    return !wasUnderscore;
}
const PredefinedFormatToCheckFunction = {
    [PredefinedFormats.PascalCase]: isPascalCase,
    [PredefinedFormats.StrictPascalCase]: isStrictPascalCase,
    [PredefinedFormats.camelCase]: isCamelCase,
    [PredefinedFormats.strictCamelCase]: isStrictCamelCase,
    [PredefinedFormats.UPPER_CASE]: isUpperCase,
    [PredefinedFormats.snake_case]: isSnakeCase,
};
// #endregion Predefined Format Functions
function selectorTypeToMessageString(selectorType) {
    const notCamelCase = selectorType.replace(/([A-Z])/g, ' $1');
    return notCamelCase.charAt(0).toUpperCase() + notCamelCase.slice(1);
}
exports.selectorTypeToMessageString = selectorTypeToMessageString;
function isMetaSelector(selector) {
    return selector in MetaSelectors;
}
function normalizeOption(option) {
    var _a, _b, _c, _d, _e, _f;
    let weight = 0;
    (_a = option.modifiers) === null || _a === void 0 ? void 0 : _a.forEach(mod => {
        weight |= Modifiers[mod];
    });
    (_b = option.types) === null || _b === void 0 ? void 0 : _b.forEach(mod => {
        weight |= TypeModifiers[mod];
    });
    // give selectors with a filter the _highest_ priority
    if (option.filter) {
        weight |= 1 << 30;
    }
    return {
        // format options
        format: option.format ? option.format.map(f => PredefinedFormats[f]) : null,
        custom: option.custom
            ? {
                regex: new RegExp(option.custom.regex),
                match: option.custom.match,
            }
            : null,
        leadingUnderscore: option.leadingUnderscore !== undefined
            ? UnderscoreOptions[option.leadingUnderscore]
            : null,
        trailingUnderscore: option.trailingUnderscore !== undefined
            ? UnderscoreOptions[option.trailingUnderscore]
            : null,
        prefix: option.prefix && option.prefix.length > 0 ? option.prefix : null,
        suffix: option.suffix && option.suffix.length > 0 ? option.suffix : null,
        // selector options
        selector: isMetaSelector(option.selector)
            ? MetaSelectors[option.selector]
            : Selectors[option.selector],
        modifiers: (_d = (_c = option.modifiers) === null || _c === void 0 ? void 0 : _c.map(m => Modifiers[m])) !== null && _d !== void 0 ? _d : null,
        types: (_f = (_e = option.types) === null || _e === void 0 ? void 0 : _e.map(m => TypeModifiers[m])) !== null && _f !== void 0 ? _f : null,
        filter: option.filter !== undefined
            ? typeof option.filter === 'string'
                ? { regex: new RegExp(option.filter), match: true }
                : {
                    regex: new RegExp(option.filter.regex),
                    match: option.filter.match,
                }
            : null,
        // calculated ordering weight based on modifiers
        modifierWeight: weight,
    };
}
function isCorrectType(node, config, context) {
    if (config.types === null) {
        return true;
    }
    const { esTreeNodeToTSNodeMap, program } = util.getParserServices(context);
    const checker = program.getTypeChecker();
    const tsNode = esTreeNodeToTSNodeMap.get(node);
    const type = checker
        .getTypeAtLocation(tsNode)
        // remove null and undefined from the type, as we don't care about it here
        .getNonNullableType();
    for (const allowedType of config.types) {
        switch (allowedType) {
            case TypeModifiers.array:
                if (isAllTypesMatch(type, t => checker.isArrayType(t) || checker.isTupleType(t))) {
                    return true;
                }
                break;
            case TypeModifiers.function:
                if (isAllTypesMatch(type, t => t.getCallSignatures().length > 0)) {
                    return true;
                }
                break;
            case TypeModifiers.boolean:
            case TypeModifiers.number:
            case TypeModifiers.string: {
                const typeString = checker.typeToString(
                // this will resolve things like true => boolean, 'a' => string and 1 => number
                checker.getWidenedType(checker.getBaseTypeOfLiteralType(type)));
                const allowedTypeString = TypeModifiers[allowedType];
                if (typeString === allowedTypeString) {
                    return true;
                }
                break;
            }
        }
    }
    return false;
}
/**
 * @returns `true` if the type (or all union types) in the given type return true for the callback
 */
function isAllTypesMatch(type, cb) {
    if (type.isUnion()) {
        return type.types.every(t => cb(t));
    }
    return cb(type);
}
//# sourceMappingURL=naming-convention.js.map