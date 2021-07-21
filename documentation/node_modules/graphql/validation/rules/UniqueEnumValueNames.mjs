import { GraphQLError } from '../../error/GraphQLError';
import { isEnumType } from '../../type/definition';
export function duplicateEnumValueNameMessage(typeName, valueName) {
  return "Enum value \"".concat(typeName, ".").concat(valueName, "\" can only be defined once.");
}
export function existedEnumValueNameMessage(typeName, valueName) {
  return "Enum value \"".concat(typeName, ".").concat(valueName, "\" already exists in the schema. It cannot also be defined in this type extension.");
}
/**
 * Unique enum value names
 *
 * A GraphQL enum type is only valid if all its values are uniquely named.
 */

export function UniqueEnumValueNames(context) {
  var schema = context.getSchema();
  var existingTypeMap = schema ? schema.getTypeMap() : Object.create(null);
  var knownValueNames = Object.create(null);
  return {
    EnumTypeDefinition: checkValueUniqueness,
    EnumTypeExtension: checkValueUniqueness
  };

  function checkValueUniqueness(node) {
    var typeName = node.name.value;

    if (!knownValueNames[typeName]) {
      knownValueNames[typeName] = Object.create(null);
    }

    if (node.values) {
      var valueNames = knownValueNames[typeName];

      for (var _i2 = 0, _node$values2 = node.values; _i2 < _node$values2.length; _i2++) {
        var valueDef = _node$values2[_i2];
        var valueName = valueDef.name.value;
        var existingType = existingTypeMap[typeName];

        if (isEnumType(existingType) && existingType.getValue(valueName)) {
          context.reportError(new GraphQLError(existedEnumValueNameMessage(typeName, valueName), valueDef.name));
        } else if (valueNames[valueName]) {
          context.reportError(new GraphQLError(duplicateEnumValueNameMessage(typeName, valueName), [valueNames[valueName], valueDef.name]));
        } else {
          valueNames[valueName] = valueDef.name;
        }
      }
    }

    return false;
  }
}
