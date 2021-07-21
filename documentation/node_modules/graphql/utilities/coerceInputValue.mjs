import { forEach, isCollection } from 'iterall';
import objectValues from '../polyfills/objectValues';
import inspect from '../jsutils/inspect';
import invariant from '../jsutils/invariant';
import didYouMean from '../jsutils/didYouMean';
import isObjectLike from '../jsutils/isObjectLike';
import suggestionList from '../jsutils/suggestionList';
import printPathArray from '../jsutils/printPathArray';
import { addPath, pathToArray } from '../jsutils/Path';
import { GraphQLError } from '../error/GraphQLError';
import { isScalarType, isEnumType, isInputObjectType, isListType, isNonNullType } from '../type/definition';

/**
 * Coerces a JavaScript value given a GraphQL Input Type.
 */
export function coerceInputValue(inputValue, type) {
  var onError = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : defaultOnError;
  return coerceInputValueImpl(inputValue, type, onError);
}

function defaultOnError(path, invalidValue, error) {
  var errorPrefix = 'Invalid value ' + inspect(invalidValue);

  if (path.length > 0) {
    errorPrefix += " at \"value".concat(printPathArray(path), "\": ");
  }

  error.message = errorPrefix + ': ' + error.message;
  throw error;
}

function coerceInputValueImpl(inputValue, type, onError, path) {
  if (isNonNullType(type)) {
    if (inputValue != null) {
      return coerceInputValueImpl(inputValue, type.ofType, onError, path);
    }

    onError(pathToArray(path), inputValue, new GraphQLError("Expected non-nullable type ".concat(inspect(type), " not to be null.")));
    return;
  }

  if (inputValue == null) {
    // Explicitly return the value null.
    return null;
  }

  if (isListType(type)) {
    var itemType = type.ofType;

    if (isCollection(inputValue)) {
      var coercedValue = [];
      forEach(inputValue, function (itemValue, index) {
        coercedValue.push(coerceInputValueImpl(itemValue, itemType, onError, addPath(path, index)));
      });
      return coercedValue;
    } // Lists accept a non-list value as a list of one.


    return [coerceInputValueImpl(inputValue, itemType, onError, path)];
  }

  if (isInputObjectType(type)) {
    if (!isObjectLike(inputValue)) {
      onError(pathToArray(path), inputValue, new GraphQLError("Expected type ".concat(type.name, " to be an object.")));
      return;
    }

    var _coercedValue = {};
    var fieldDefs = type.getFields();

    for (var _i2 = 0, _objectValues2 = objectValues(fieldDefs); _i2 < _objectValues2.length; _i2++) {
      var field = _objectValues2[_i2];
      var fieldValue = inputValue[field.name];

      if (fieldValue === undefined) {
        if (field.defaultValue !== undefined) {
          _coercedValue[field.name] = field.defaultValue;
        } else if (isNonNullType(field.type)) {
          var typeStr = inspect(field.type);
          onError(pathToArray(path), inputValue, new GraphQLError("Field ".concat(field.name, " of required type ").concat(typeStr, " was not provided.")));
        }

        continue;
      }

      _coercedValue[field.name] = coerceInputValueImpl(fieldValue, field.type, onError, addPath(path, field.name));
    } // Ensure every provided field is defined.


    for (var _i4 = 0, _Object$keys2 = Object.keys(inputValue); _i4 < _Object$keys2.length; _i4++) {
      var fieldName = _Object$keys2[_i4];

      if (!fieldDefs[fieldName]) {
        var suggestions = suggestionList(fieldName, Object.keys(type.getFields()));
        onError(pathToArray(path), inputValue, new GraphQLError("Field \"".concat(fieldName, "\" is not defined by type ").concat(type.name, ".") + didYouMean(suggestions)));
      }
    }

    return _coercedValue;
  }

  if (isScalarType(type)) {
    var parseResult; // Scalars determine if a input value is valid via parseValue(), which can
    // throw to indicate failure. If it throws, maintain a reference to
    // the original error.

    try {
      parseResult = type.parseValue(inputValue);
    } catch (error) {
      onError(pathToArray(path), inputValue, new GraphQLError("Expected type ".concat(type.name, ". ") + error.message, undefined, undefined, undefined, undefined, error));
      return;
    }

    if (parseResult === undefined) {
      onError(pathToArray(path), inputValue, new GraphQLError("Expected type ".concat(type.name, ".")));
    }

    return parseResult;
  }

  /* istanbul ignore else */
  if (isEnumType(type)) {
    if (typeof inputValue === 'string') {
      var enumValue = type.getValue(inputValue);

      if (enumValue) {
        return enumValue.value;
      }
    }

    var _suggestions = suggestionList(String(inputValue), type.getValues().map(function (enumValue) {
      return enumValue.name;
    }));

    onError(pathToArray(path), inputValue, new GraphQLError("Expected type ".concat(type.name, ".") + didYouMean(_suggestions)));
    return;
  } // Not reachable. All possible input types have been considered.


  /* istanbul ignore next */
  invariant(false, 'Unexpected input type: ' + inspect(type));
}
