"use strict";

exports.__esModule = true;
exports.getPagination = exports.getGroup = exports.getEdge = exports.getPageInfo = void 0;

var _sort = require("./sort");

var _derivedTypes = require("./derived-types");

var _resolvers = require("../resolvers");

const getPageInfo = ({
  schemaComposer
}) => schemaComposer.getOrCreateOTC(`PageInfo`, tc => {
  tc.addFields({
    currentPage: `Int!`,
    hasPreviousPage: `Boolean!`,
    hasNextPage: `Boolean!`,
    itemCount: `Int!`,
    pageCount: `Int!`,
    perPage: `Int`,
    totalCount: `Int!`
  });
});

exports.getPageInfo = getPageInfo;

const getEdge = ({
  schemaComposer,
  typeComposer
}) => {
  const typeName = `${typeComposer.getTypeName()}Edge`;
  (0, _derivedTypes.addDerivedType)({
    typeComposer,
    derivedTypeName: typeName
  });
  return schemaComposer.getOrCreateOTC(typeName, tc => {
    tc.addFields({
      next: typeComposer,
      node: typeComposer.getTypeNonNull(),
      previous: typeComposer
    });
  });
};

exports.getEdge = getEdge;

const createPagination = ({
  schemaComposer,
  typeComposer,
  fields,
  typeName
}) => {
  const paginationTypeComposer = schemaComposer.getOrCreateOTC(typeName, tc => {
    tc.addFields({
      totalCount: `Int!`,
      edges: [getEdge({
        schemaComposer,
        typeComposer
      }).getTypeNonNull()],
      nodes: [typeComposer.getTypeNonNull()],
      pageInfo: getPageInfo({
        schemaComposer
      }).getTypeNonNull(),
      ...fields
    });
  });
  paginationTypeComposer.makeFieldNonNull(`edges`);
  paginationTypeComposer.makeFieldNonNull(`nodes`);
  (0, _derivedTypes.addDerivedType)({
    typeComposer,
    derivedTypeName: typeName
  });
  return paginationTypeComposer;
};

const getGroup = ({
  schemaComposer,
  typeComposer
}) => {
  const typeName = `${typeComposer.getTypeName()}GroupConnection`;
  const fields = {
    field: `String!`,
    fieldValue: `String`
  };
  return createPagination({
    schemaComposer,
    typeComposer,
    fields,
    typeName
  });
};

exports.getGroup = getGroup;

const getPagination = ({
  schemaComposer,
  typeComposer
}) => {
  const inputTypeComposer = typeComposer.getInputTypeComposer();
  const typeName = `${typeComposer.getTypeName()}Connection`;
  const fieldsEnumTC = (0, _sort.getFieldsEnum)({
    schemaComposer,
    typeComposer,
    inputTypeComposer
  });
  const fields = {
    distinct: {
      type: [`String!`],
      args: {
        field: fieldsEnumTC.getTypeNonNull()
      },
      resolve: _resolvers.distinct
    },
    group: {
      type: [getGroup({
        schemaComposer,
        typeComposer
      }).getTypeNonNull()],
      args: {
        skip: `Int`,
        limit: `Int`,
        field: fieldsEnumTC.getTypeNonNull()
      },
      resolve: _resolvers.group
    }
  };
  const paginationTypeComposer = createPagination({
    schemaComposer,
    typeComposer,
    fields,
    typeName
  });
  paginationTypeComposer.makeFieldNonNull(`distinct`);
  paginationTypeComposer.makeFieldNonNull(`group`);
  return paginationTypeComposer;
};

exports.getPagination = getPagination;
//# sourceMappingURL=pagination.js.map