"use strict";

exports.__esModule = true;
exports.getFilterInput = exports.SEARCHABLE_ENUM = void 0;

var _graphql = require("graphql");

var _derivedTypes = require("./derived-types");

var _graphqlCompose = require("graphql-compose");

var _date = require("./date");

const SEARCHABLE_ENUM = {
  SEARCHABLE: `SEARCHABLE`,
  NOT_SEARCHABLE: `NON_SEARCHABLE`,
  DEPRECATED_SEARCHABLE: `DERPECATED_SEARCHABLE`
};
exports.SEARCHABLE_ENUM = SEARCHABLE_ENUM;

const getQueryOperatorListInput = ({
  schemaComposer,
  inputTypeComposer
}) => {
  const typeName = inputTypeComposer.getTypeName().replace(/Input/, `ListInput`);
  return schemaComposer.getOrCreateITC(typeName, itc => {
    itc.addFields({
      elemMatch: inputTypeComposer
    });
  });
};

const removeEmptyFields = ({
  inputTypeComposer
}, cache = new Set()) => {
  const convert = itc => {
    if (cache.has(itc)) {
      return itc;
    }

    cache.add(itc);
    const fields = itc.getFields();
    const nonEmptyFields = {};
    Object.keys(fields).forEach(fieldName => {
      const fieldITC = fields[fieldName];

      if (fieldITC instanceof _graphqlCompose.InputTypeComposer) {
        const convertedITC = convert(fieldITC);

        if (convertedITC.getFieldNames().length) {
          nonEmptyFields[fieldName] = convertedITC;
        }
      } else {
        nonEmptyFields[fieldName] = fieldITC;
      }
    });
    itc.setFields(nonEmptyFields);
    return itc;
  };

  return convert(inputTypeComposer);
};

const EQ = `eq`;
const NE = `ne`;
const GT = `gt`;
const GTE = `gte`;
const LT = `lt`;
const LTE = `lte`;
const IN = `in`;
const NIN = `nin`;
const REGEX = `regex`;
const GLOB = `glob`;
const ALLOWED_OPERATORS = {
  Boolean: [EQ, NE, IN, NIN],
  Date: [EQ, NE, GT, GTE, LT, LTE, IN, NIN],
  Float: [EQ, NE, GT, GTE, LT, LTE, IN, NIN],
  ID: [EQ, NE, IN, NIN],
  Int: [EQ, NE, GT, GTE, LT, LTE, IN, NIN],
  JSON: [EQ, NE, IN, NIN, REGEX, GLOB],
  String: [EQ, NE, IN, NIN, REGEX, GLOB],
  Enum: [EQ, NE, IN, NIN],
  CustomScalar: [EQ, NE, IN, NIN]
};
const ARRAY_OPERATORS = [IN, NIN];

const getOperatorFields = (fieldType, operators) => {
  const result = {};
  operators.forEach(op => {
    if (ARRAY_OPERATORS.includes(op)) {
      result[op] = [fieldType];
    } else {
      result[op] = fieldType;
    }
  });
  return result;
};

const isBuiltInScalarType = type => (0, _graphql.isSpecifiedScalarType)(type) || type === _date.GraphQLDate || type === _graphqlCompose.GraphQLJSON;

const getQueryOperatorInput = ({
  schemaComposer,
  type
}) => {
  let typeName;

  if (type instanceof _graphql.GraphQLEnumType) {
    typeName = `Enum`;
  } else if (isBuiltInScalarType(type)) {
    typeName = type.name;
  } else {
    typeName = `CustomScalar`;
  }

  const operators = ALLOWED_OPERATORS[typeName];
  return schemaComposer.getOrCreateITC(type.name + `QueryOperatorInput`, itc => itc.addFields(getOperatorFields(type, operators)));
};

const convert = ({
  schemaComposer,
  typeComposer,
  inputTypeComposer,
  filterInputComposer,
  deprecationReason
}) => {
  const inputTypeName = inputTypeComposer.getTypeName().replace(/Input$/, `FilterInput`);
  (0, _derivedTypes.addDerivedType)({
    typeComposer,
    derivedTypeName: inputTypeName
  });
  let convertedITC;

  if (filterInputComposer) {
    convertedITC = filterInputComposer;
  } else if (schemaComposer.has(inputTypeName)) {
    return schemaComposer.getITC(inputTypeName);
  } else {
    convertedITC = new _graphqlCompose.InputTypeComposer(new _graphql.GraphQLInputObjectType({
      name: inputTypeName,
      fields: {}
    }), schemaComposer);
  }

  schemaComposer.addAsComposer(convertedITC);
  const fieldNames = inputTypeComposer.getFieldNames();
  const convertedFields = {};
  fieldNames.forEach(fieldName => {
    const fieldConfig = inputTypeComposer.getFieldConfig(fieldName);
    const type = (0, _graphql.getNamedType)(fieldConfig.type);
    const searchable = typeComposer instanceof _graphqlCompose.UnionTypeComposer || typeComposer instanceof _graphqlCompose.ScalarTypeComposer ? undefined : typeComposer.getFieldExtension(fieldName, `searchable`);

    if (searchable === SEARCHABLE_ENUM.NOT_SEARCHABLE) {
      return;
    } else if (searchable === SEARCHABLE_ENUM.DEPRECATED_SEARCHABLE) {
      deprecationReason = `Filtering on fields that need arguments to resolve is deprecated.`;
    }

    if (type instanceof _graphql.GraphQLInputObjectType) {
      // Input type composers has names `FooInput`, get the type associated
      // with it
      const typeComposer = schemaComposer.getAnyTC(type.name.replace(/Input$/, ``));
      const itc = new _graphqlCompose.InputTypeComposer(type, schemaComposer);
      const operatorsInputTC = convert({
        schemaComposer,
        typeComposer,
        inputTypeComposer: itc,
        deprecationReason
      }); // TODO: array of arrays?

      const isListType = (0, _graphql.getNullableType)(fieldConfig.type) instanceof _graphql.GraphQLList; // elemMatch operator


      convertedFields[fieldName] = isListType ? getQueryOperatorListInput({
        schemaComposer,
        inputTypeComposer: operatorsInputTC
      }) : operatorsInputTC;
    } else {
      // GraphQLScalarType || GraphQLEnumType
      const operatorFields = getQueryOperatorInput({
        schemaComposer,
        type
      });

      if (operatorFields) {
        convertedFields[fieldName] = operatorFields;
      }
    }

    if (convertedFields[fieldName]) {
      convertedFields[fieldName].deprecationReason = deprecationReason;
    }
  });
  convertedITC.addFields(convertedFields);
  return convertedITC;
};

const getFilterInput = ({
  schemaComposer,
  typeComposer
}) => {
  const typeName = typeComposer.getTypeName();
  const filterInputComposer = schemaComposer.getOrCreateITC(`${typeName}FilterInput`);
  const inputTypeComposer = typeComposer.getInputTypeComposer(); // TODO: In Gatsby v2, the NodeInput.id field is of type String, not ID.
  // Remove this workaround for v3.

  if ((inputTypeComposer === null || inputTypeComposer === void 0 ? void 0 : inputTypeComposer.hasField(`id`)) && (0, _graphql.getNamedType)(inputTypeComposer.getFieldType(`id`)).name === `ID`) {
    inputTypeComposer.extendField(`id`, {
      type: `String`
    });
  }

  const filterInputTC = convert({
    schemaComposer,
    typeComposer,
    inputTypeComposer,
    filterInputComposer
  });
  return removeEmptyFields({
    inputTypeComposer: filterInputTC
  });
};

exports.getFilterInput = getFilterInput;
//# sourceMappingURL=filter.js.map