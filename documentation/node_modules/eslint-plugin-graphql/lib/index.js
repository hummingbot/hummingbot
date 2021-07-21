"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard");

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = exports.processors = exports.rules = void 0;

var _fs = _interopRequireDefault(require("fs"));

var _path = _interopRequireDefault(require("path"));

var _graphql = require("graphql");

var _lodash = _interopRequireDefault(require("lodash.flatten"));

var _lodash2 = _interopRequireDefault(require("lodash.without"));

var _graphqlConfig = require("graphql-config");

var customRules = _interopRequireWildcard(require("./customGraphQLValidationRules"));

var _constants = require("./constants");

var _createRule = require("./createRule");

const allGraphQLValidatorNames = _graphql.specifiedRules.map(rule => rule.name); // Map of env name to list of rule names.


const envGraphQLValidatorNames = {
  apollo: (0, _lodash2.default)(allGraphQLValidatorNames, "KnownFragmentNames", "NoUnusedFragments", // `graphql`@15
  "KnownFragmentNamesRule", "NoUnusedFragmentsRule"),
  lokka: (0, _lodash2.default)(allGraphQLValidatorNames, "KnownFragmentNames", "NoUnusedFragments", // `graphql`@15
  "KnownFragmentNamesRule", "NoUnusedFragmentsRule"),
  fraql: (0, _lodash2.default)(allGraphQLValidatorNames, "KnownFragmentNames", "NoUnusedFragments", // `graphql`@15
  "KnownFragmentNamesRule", "NoUnusedFragmentsRule"),
  relay: (0, _lodash2.default)(allGraphQLValidatorNames, "KnownDirectives", "KnownFragmentNames", "NoUndefinedVariables", "NoUnusedFragments", // `graphql`@15
  "KnownDirectivesRule", "KnownFragmentNamesRule", "NoUndefinedVariablesRule", "NoUnusedFragmentsRule", // `graphql` < 14
  "ProvidedNonNullArguments", // `graphql`@14
  "ProvidedRequiredArguments", "ScalarLeafs", // `graphql`@15
  "ProvidedRequiredArgumentsRule", "ScalarLeafsRule"),
  literal: (0, _lodash2.default)(allGraphQLValidatorNames, "KnownFragmentNames", "NoUnusedFragments", // `graphql`@15
  "KnownFragmentNamesRule", "NoUnusedFragmentsRule")
};
const gqlFiles = ["gql", "graphql"];
const defaultRuleProperties = {
  env: {
    enum: ["lokka", "fraql", "relay", "apollo", "literal"]
  },
  schemaJson: {
    type: "object"
  },
  schemaJsonFilepath: {
    type: "string"
  },
  schemaString: {
    type: "string"
  },
  tagName: {
    type: "string",
    pattern: "^[$_a-zA-Z$_][a-zA-Z0-9$_]+(\\.[a-zA-Z0-9$_]+)?$"
  },
  projectName: {
    type: "string"
  }
}; // schemaJson, schemaJsonFilepath, schemaString and projectName are mutually exclusive:

const schemaPropsExclusiveness = {
  oneOf: [{
    required: ["schemaJson"],
    not: {
      required: ["schemaString", "schemaJsonFilepath", "projectName"]
    }
  }, {
    required: ["schemaJsonFilepath"],
    not: {
      required: ["schemaJson", "schemaString", "projectName"]
    }
  }, {
    required: ["schemaString"],
    not: {
      required: ["schemaJson", "schemaJsonFilepath", "projectName"]
    }
  }, {
    not: {
      anyOf: [{
        required: ["schemaString"]
      }, {
        required: ["schemaJson"]
      }, {
        required: ["schemaJsonFilepath"]
      }]
    }
  }]
};
const rules = {
  "template-strings": {
    meta: {
      schema: {
        type: "array",
        items: {
          additionalProperties: false,
          properties: { ...defaultRuleProperties,
            validators: {
              oneOf: [{
                type: "array",
                uniqueItems: true,
                items: {
                  enum: allGraphQLValidatorNames
                }
              }, {
                enum: ["all"]
              }]
            }
          },
          ...schemaPropsExclusiveness
        }
      }
    },
    create: context => (0, _createRule.createRule)(context, optionGroup => parseOptions(optionGroup, context))
  },
  "named-operations": {
    meta: {
      schema: {
        type: "array",
        items: {
          additionalProperties: false,
          properties: { ...defaultRuleProperties
          },
          ...schemaPropsExclusiveness
        }
      }
    },
    create: context => {
      return (0, _createRule.createRule)(context, optionGroup => parseOptions({
        validators: ["OperationsMustHaveNames"],
        ...optionGroup
      }, context));
    }
  },
  "required-fields": {
    meta: {
      schema: {
        type: "array",
        minItems: 1,
        items: {
          additionalProperties: false,
          properties: { ...defaultRuleProperties,
            requiredFields: {
              type: "array",
              items: {
                type: "string"
              }
            }
          },
          required: ["requiredFields"],
          ...schemaPropsExclusiveness
        }
      }
    },
    create: context => {
      return (0, _createRule.createRule)(context, optionGroup => parseOptions({
        validators: ["RequiredFields"],
        options: {
          requiredFields: optionGroup.requiredFields
        },
        ...optionGroup
      }, context));
    }
  },
  "capitalized-type-name": {
    meta: {
      schema: {
        type: "array",
        items: {
          additionalProperties: false,
          properties: { ...defaultRuleProperties
          },
          ...schemaPropsExclusiveness
        }
      }
    },
    create: context => {
      return (0, _createRule.createRule)(context, optionGroup => parseOptions({
        validators: ["typeNamesShouldBeCapitalized"],
        ...optionGroup
      }, context));
    }
  },
  "no-deprecated-fields": {
    meta: {
      schema: {
        type: "array",
        items: {
          additionalProperties: false,
          properties: { ...defaultRuleProperties
          },
          ...schemaPropsExclusiveness
        }
      }
    },
    create: context => {
      return (0, _createRule.createRule)(context, optionGroup => parseOptions({
        validators: ["noDeprecatedFields"],
        ...optionGroup
      }, context));
    }
  }
};
exports.rules = rules;
const schemaCache = {};
const projectCache = {};

function parseOptions(optionGroup, context) {
  const {
    schemaJson,
    // Schema via JSON object
    schemaJsonFilepath,
    // Or Schema via absolute filepath
    schemaString,
    // Or Schema as string,
    env,
    projectName,
    tagName: tagNameOption,
    validators: validatorNamesOption
  } = optionGroup;
  const cacheHit = schemaCache[JSON.stringify(optionGroup)];

  if (cacheHit && env !== "literal") {
    return cacheHit;
  } // Validate and unpack schema


  let schema;

  if (schemaJson) {
    schema = initSchema(schemaJson);
  } else if (schemaJsonFilepath) {
    schema = initSchemaFromFile(schemaJsonFilepath);
  } else if (schemaString) {
    schema = initSchemaFromString(schemaString);
  } else {
    try {
      const config = (0, _graphqlConfig.loadConfigSync)({
        rootDir: _path.default.resolve(process.cwd(), _path.default.dirname(context.getFilename()))
      });
      let projectConfig;

      if (projectName) {
        projectConfig = config.getProject(projectName);

        if (!projectConfig) {
          throw new Error(`Project with name "${projectName}" not found in ${config.filepath}.`);
        }
      } else {
        try {
          projectConfig = config.getProjectForFile(context.getFilename());
        } catch (e) {
          if (!(e instanceof _graphqlConfig.ProjectNotFoundError)) {
            throw e;
          }
        }
      }

      if (projectConfig) {
        const key = `${config.filepath}[${projectConfig.name}]`;
        schema = projectCache[key];

        if (!schema) {
          schema = projectConfig.getSchemaSync();
          projectCache[key] = schema;
        }
      }

      if (cacheHit) {
        return { ...cacheHit,
          schema
        };
      }
    } catch (e) {
      if (e instanceof _graphqlConfig.ConfigNotFoundError) {
        throw new Error("Must provide GraphQL Config file or pass in `schemaJson` option " + "with schema object or `schemaJsonFilepath` with absolute path to the json file.");
      }

      throw e;
    }
  } // Validate env


  if (env && env !== "lokka" && env !== "fraql" && env !== "relay" && env !== "apollo" && env !== "literal") {
    throw new Error("Invalid option for env, only `apollo`, `lokka`, `fraql`, `relay`, and `literal` supported.");
  } // Validate tagName and set default


  let tagName;

  if (tagNameOption) {
    tagName = tagNameOption;
  } else if (env === "relay") {
    tagName = "Relay.QL";
  } else if (env === "literal") {
    tagName = _constants.internalTag;
  } else {
    tagName = "gql";
  } // The validator list may be:
  //    The string 'all' to use all rules.
  //    An array of rule names.
  //    null/undefined to use the default rule set of the environment, or all rules.


  let validatorNames;

  if (validatorNamesOption === "all") {
    validatorNames = allGraphQLValidatorNames;
  } else if (validatorNamesOption) {
    validatorNames = validatorNamesOption;
  } else {
    validatorNames = envGraphQLValidatorNames[env] || allGraphQLValidatorNames;
  }

  const validators = validatorNames.map(name => {
    if (name in customRules) {
      return customRules[name];
    } else {
      return require(`graphql/validation/rules/${name}`)[name];
    }
  });
  const results = {
    schema,
    env,
    tagName,
    validators
  };
  schemaCache[JSON.stringify(optionGroup)] = results;
  return results;
}

function initSchema(json) {
  const unpackedSchemaJson = json.data ? json.data : json;

  if (!unpackedSchemaJson.__schema) {
    throw new Error("Please pass a valid GraphQL introspection query result.");
  }

  return (0, _graphql.buildClientSchema)(unpackedSchemaJson);
}

function initSchemaFromFile(jsonFile) {
  return initSchema(JSON.parse(_fs.default.readFileSync(jsonFile, "utf8")));
}

function initSchemaFromString(source) {
  return (0, _graphql.buildSchema)(source);
}

const gqlProcessor = {
  preprocess: function (text) {
    // Wrap the text in backticks and prepend the internal tag. First the text
    // must be escaped, because of the three sequences that have special
    // meaning in JavaScript template literals, and could change the meaning of
    // the text or cause syntax errors.
    // https://tc39.github.io/ecma262/#prod-TemplateCharacter
    //
    // - "`" would end the template literal.
    // - "\" would start an escape sequence.
    // - "${" would start an interpolation.
    const escaped = text.replace(/[`\\]|\$\{/g, "\\$&");
    return [`${_constants.internalTag}\`${escaped}\``];
  },
  postprocess: function (messages) {
    // only report graphql-errors
    return (0, _lodash.default)(messages).filter(message => Object.keys(rules).map(key => `graphql/${key}`).includes(message.ruleId));
  }
};
const processors = gqlFiles.reduce((result, value) => {
  return { ...result,
    [`.${value}`]: gqlProcessor
  };
}, {});
exports.processors = processors;
var _default = {
  rules,
  processors
};
exports.default = _default;