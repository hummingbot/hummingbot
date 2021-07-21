import { GraphQLError } from '../../error/GraphQLError';
import { isObjectType, isInterfaceType, isInputObjectType } from '../../type/definition';
export function duplicateFieldDefinitionNameMessage(typeName, fieldName) {
  return "Field \"".concat(typeName, ".").concat(fieldName, "\" can only be defined once.");
}
export function existedFieldDefinitionNameMessage(typeName, fieldName) {
  return "Field \"".concat(typeName, ".").concat(fieldName, "\" already exists in the schema. It cannot also be defined in this type extension.");
}
/**
 * Unique field definition names
 *
 * A GraphQL complex type is only valid if all its fields are uniquely named.
 */

export function UniqueFieldDefinitionNames(context) {
  var schema = context.getSchema();
  var existingTypeMap = schema ? schema.getTypeMap() : Object.create(null);
  var knownFieldNames = Object.create(null);
  return {
    InputObjectTypeDefinition: checkFieldUniqueness,
    InputObjectTypeExtension: checkFieldUniqueness,
    InterfaceTypeDefinition: checkFieldUniqueness,
    InterfaceTypeExtension: checkFieldUniqueness,
    ObjectTypeDefinition: checkFieldUniqueness,
    ObjectTypeExtension: checkFieldUniqueness
  };

  function checkFieldUniqueness(node) {
    var typeName = node.name.value;

    if (!knownFieldNames[typeName]) {
      knownFieldNames[typeName] = Object.create(null);
    }

    if (node.fields) {
      var fieldNames = knownFieldNames[typeName];

      for (var _i2 = 0, _node$fields2 = node.fields; _i2 < _node$fields2.length; _i2++) {
        var fieldDef = _node$fields2[_i2];
        var fieldName = fieldDef.name.value;

        if (hasField(existingTypeMap[typeName], fieldName)) {
          context.reportError(new GraphQLError(existedFieldDefinitionNameMessage(typeName, fieldName), fieldDef.name));
        } else if (fieldNames[fieldName]) {
          context.reportError(new GraphQLError(duplicateFieldDefinitionNameMessage(typeName, fieldName), [fieldNames[fieldName], fieldDef.name]));
        } else {
          fieldNames[fieldName] = fieldDef.name;
        }
      }
    }

    return false;
  }
}

function hasField(type, fieldName) {
  if (isObjectType(type) || isInterfaceType(type) || isInputObjectType(type)) {
    return type.getFields()[fieldName];
  }

  return false;
}
