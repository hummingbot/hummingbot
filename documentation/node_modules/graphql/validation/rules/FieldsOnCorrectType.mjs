import didYouMean from '../../jsutils/didYouMean';
import suggestionList from '../../jsutils/suggestionList';
import { GraphQLError } from '../../error/GraphQLError';
import { isObjectType, isInterfaceType, isAbstractType } from '../../type/definition';
export function undefinedFieldMessage(fieldName, type, suggestedTypeNames, suggestedFieldNames) {
  var quotedTypeNames = suggestedTypeNames.map(function (x) {
    return "\"".concat(x, "\"");
  });
  var quotedFieldNames = suggestedFieldNames.map(function (x) {
    return "\"".concat(x, "\"");
  });
  return "Cannot query field \"".concat(fieldName, "\" on type \"").concat(type, "\".") + (didYouMean('to use an inline fragment on', quotedTypeNames) || didYouMean(quotedFieldNames));
}
/**
 * Fields on correct type
 *
 * A GraphQL document is only valid if all fields selected are defined by the
 * parent type, or are an allowed meta field such as __typename.
 */

export function FieldsOnCorrectType(context) {
  return {
    Field: function Field(node) {
      var type = context.getParentType();

      if (type) {
        var fieldDef = context.getFieldDef();

        if (!fieldDef) {
          // This field doesn't exist, lets look for suggestions.
          var schema = context.getSchema();
          var fieldName = node.name.value; // First determine if there are any suggested types to condition on.

          var suggestedTypeNames = getSuggestedTypeNames(schema, type, fieldName); // If there are no suggested types, then perhaps this was a typo?

          var suggestedFieldNames = suggestedTypeNames.length !== 0 ? [] : getSuggestedFieldNames(schema, type, fieldName); // Report an error, including helpful suggestions.

          context.reportError(new GraphQLError(undefinedFieldMessage(fieldName, type.name, suggestedTypeNames, suggestedFieldNames), node));
        }
      }
    }
  };
}
/**
 * Go through all of the implementations of type, as well as the interfaces that
 * they implement. If any of those types include the provided field, suggest
 * them, sorted by how often the type is referenced, starting with Interfaces.
 */

function getSuggestedTypeNames(schema, type, fieldName) {
  if (isAbstractType(type)) {
    var suggestedObjectTypes = [];
    var interfaceUsageCount = Object.create(null);

    for (var _i2 = 0, _schema$getPossibleTy2 = schema.getPossibleTypes(type); _i2 < _schema$getPossibleTy2.length; _i2++) {
      var possibleType = _schema$getPossibleTy2[_i2];

      if (!possibleType.getFields()[fieldName]) {
        continue;
      } // This object type defines this field.


      suggestedObjectTypes.push(possibleType.name);

      for (var _i4 = 0, _possibleType$getInte2 = possibleType.getInterfaces(); _i4 < _possibleType$getInte2.length; _i4++) {
        var possibleInterface = _possibleType$getInte2[_i4];

        if (!possibleInterface.getFields()[fieldName]) {
          continue;
        } // This interface type defines this field.


        interfaceUsageCount[possibleInterface.name] = (interfaceUsageCount[possibleInterface.name] || 0) + 1;
      }
    } // Suggest interface types based on how common they are.


    var suggestedInterfaceTypes = Object.keys(interfaceUsageCount).sort(function (a, b) {
      return interfaceUsageCount[b] - interfaceUsageCount[a];
    }); // Suggest both interface and object types.

    return suggestedInterfaceTypes.concat(suggestedObjectTypes);
  } // Otherwise, must be an Object type, which does not have possible fields.


  return [];
}
/**
 * For the field name provided, determine if there are any similar field names
 * that may be the result of a typo.
 */


function getSuggestedFieldNames(schema, type, fieldName) {
  if (isObjectType(type) || isInterfaceType(type)) {
    var possibleFieldNames = Object.keys(type.getFields());
    return suggestionList(fieldName, possibleFieldNames);
  } // Otherwise, must be a Union type, which does not define fields.


  return [];
}
