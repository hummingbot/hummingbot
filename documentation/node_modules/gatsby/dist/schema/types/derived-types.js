"use strict";

exports.__esModule = true;
exports.addDerivedType = exports.clearDerivedTypes = void 0;

var _graphqlCompose = require("graphql-compose");

/**
 * Derived types are types that make sense only when their base type exists
 *
 * Take this node for example:
 * {
 *   internal: { type: 'Foo' },
 *   fields: {
 *     bar: "string",
 *   }
 * }
 *
 * It will produce following types:
 * Foo
 * FooFields
 *
 * FooInputFilter
 * FooSortInput
 *
 * FooFieldsInputFilter
 * FooFieldsSortFilter
 * etc
 *
 * Derived types:
 *   Foo: FooFields, FooInputFilter, FooSortInput
 *   FooFields: FooFieldsInputFilter, FooFieldsSortFilter
 *
 * Caveats:
 *   Only types created via inference are marked as derived. So if in the example above
 *   user explicitly defines `FooFields` type (via `createTypes` call) it won't be considered
 *   a derived type
 */
const getDerivedTypes = ({
  typeComposer
}) => typeComposer.getExtension(`derivedTypes`) || new Set();

const clearDerivedTypes = ({
  schemaComposer,
  typeComposer
}) => {
  const derivedTypes = getDerivedTypes({
    typeComposer
  });

  for (const typeName of derivedTypes.values()) {
    const derivedTypeComposer = schemaComposer.getAnyTC(typeName);
    clearDerivedTypes({
      schemaComposer,
      typeComposer: derivedTypeComposer
    });
    schemaComposer.delete(typeName);
  }

  if (typeComposer instanceof _graphqlCompose.ObjectTypeComposer || typeComposer instanceof _graphqlCompose.InterfaceTypeComposer) {
    typeComposer.removeInputTypeComposer();
  }

  typeComposer.setExtension(`derivedTypes`, new Set());
};

exports.clearDerivedTypes = clearDerivedTypes;

const addDerivedType = ({
  typeComposer,
  derivedTypeName
}) => {
  const derivedTypes = getDerivedTypes({
    typeComposer
  });
  typeComposer.setExtension(`derivedTypes`, derivedTypes.add(derivedTypeName));
};

exports.addDerivedType = addDerivedType;
//# sourceMappingURL=derived-types.js.map