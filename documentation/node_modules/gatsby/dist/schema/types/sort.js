"use strict";

exports.__esModule = true;
exports.getSortInput = exports.getFieldsEnum = exports.getSortOrderEnum = exports.SORTABLE_ENUM = void 0;

var _graphql = require("graphql");

var _derivedTypes = require("./derived-types");

var _graphqlCompose = require("graphql-compose");

const SORTABLE_ENUM = {
  SORTABLE: `SORTABLE`,
  NOT_SORTABLE: `NON_SORTABLE`,
  DEPRECATED_SORTABLE: `DERPECATED_SORTABLE`
};
exports.SORTABLE_ENUM = SORTABLE_ENUM;

const getSortOrderEnum = ({
  schemaComposer
}) => schemaComposer.getOrCreateETC(`SortOrderEnum`, etc => {
  etc.setFields({
    ASC: {
      value: `ASC`
    },
    DESC: {
      value: `DESC`
    }
  });
});

exports.getSortOrderEnum = getSortOrderEnum;
const MAX_SORT_DEPTH = 3;
const SORT_FIELD_DELIMITER = `___`;

const convert = ({
  schemaComposer,
  typeComposer,
  fields,
  prefix = null,
  depth = 0,
  deprecationReason
}) => {
  const sortFields = {};
  Object.keys(fields).forEach(fieldName => {
    const fieldConfig = fields[fieldName];
    const sortable = typeComposer instanceof _graphqlCompose.UnionTypeComposer || typeComposer instanceof _graphqlCompose.ScalarTypeComposer ? undefined : typeComposer.getFieldExtension(fieldName, `sortable`);

    if (sortable === SORTABLE_ENUM.NOT_SORTABLE) {
      return;
    } else if (sortable === SORTABLE_ENUM.DEPRECATED_SORTABLE) {
      deprecationReason = `Sorting on fields that need arguments to resolve is deprecated.`;
    }

    const sortKey = prefix ? `${prefix}.${fieldName}` : fieldName;
    const sortKeyFieldName = sortKey.split(`.`).join(SORT_FIELD_DELIMITER); // XXX(freiksenet): this is to preserve legacy behaviour, this probably doesn't actually sort

    if ((0, _graphql.getNullableType)(fieldConfig.type) instanceof _graphql.GraphQLList) {
      sortFields[sortKeyFieldName] = {
        value: sortKey,
        deprecationReason
      };
    }

    const type = (0, _graphql.getNamedType)(fieldConfig.type);

    if (type instanceof _graphql.GraphQLInputObjectType) {
      if (depth < MAX_SORT_DEPTH) {
        const typeComposer = schemaComposer.getAnyTC(type.name.replace(/Input$/, ``));
        Object.assign(sortFields, convert({
          schemaComposer,
          typeComposer,
          fields: type.getFields(),
          prefix: sortKey,
          depth: depth + 1,
          deprecationReason
        }));
      }
    } else {
      // GraphQLScalarType || GraphQLEnumType
      sortFields[sortKeyFieldName] = {
        value: sortKey,
        deprecationReason
      };
    }
  });
  return sortFields;
};

const getFieldsEnum = ({
  schemaComposer,
  typeComposer,
  inputTypeComposer
}) => {
  const typeName = typeComposer.getTypeName();
  const fieldsEnumTypeName = `${typeName}FieldsEnum`;
  const fieldsEnumTypeComposer = schemaComposer.getOrCreateETC(fieldsEnumTypeName);
  (0, _derivedTypes.addDerivedType)({
    typeComposer,
    derivedTypeName: fieldsEnumTypeName
  });
  const fields = convert({
    schemaComposer,
    typeComposer,
    fields: inputTypeComposer.getFields()
  });
  fieldsEnumTypeComposer.setFields(fields);
  return fieldsEnumTypeComposer;
};

exports.getFieldsEnum = getFieldsEnum;

const getSortInput = ({
  schemaComposer,
  typeComposer
}) => {
  const inputTypeComposer = typeComposer.getInputTypeComposer();
  const sortOrderEnumTC = getSortOrderEnum({
    schemaComposer
  });
  const fieldsEnumTC = getFieldsEnum({
    schemaComposer,
    typeComposer,
    inputTypeComposer
  });
  const typeName = typeComposer.getTypeName(); // console.log(fieldsEnumTC.getType().getValues())

  const sortInputTypeName = `${typeName}SortInput`;
  (0, _derivedTypes.addDerivedType)({
    typeComposer,
    derivedTypeName: sortInputTypeName
  });
  return schemaComposer.getOrCreateITC(sortInputTypeName, itc => {
    itc.addFields({
      fields: [fieldsEnumTC],
      order: {
        type: [sortOrderEnumTC],
        defaultValue: [`ASC`]
      }
    });
  });
};

exports.getSortInput = getSortInput;
//# sourceMappingURL=sort.js.map