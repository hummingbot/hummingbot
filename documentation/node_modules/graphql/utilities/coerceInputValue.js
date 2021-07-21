"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.coerceInputValue = coerceInputValue;

var _iterall = require("iterall");

var _objectValues3 = _interopRequireDefault(require("../polyfills/objectValues"));

var _inspect = _interopRequireDefault(require("../jsutils/inspect"));

var _invariant = _interopRequireDefault(require("../jsutils/invariant"));

var _didYouMean = _interopRequireDefault(require("../jsutils/didYouMean"));

var _isObjectLike = _interopRequireDefault(require("../jsutils/isObjectLike"));

var _suggestionList = _interopRequireDefault(require("../jsutils/suggestionList"));

var _printPathArray = _interopRequireDefault(require("../jsutils/printPathArray"));

var _Path = require("../jsutils/Path");

var _GraphQLError = require("../error/GraphQLError");

var _definition = require("../type/definition");

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

/**
 * Coerces a JavaScript value given a GraphQL Input Type.
 */
function coerceInputValue(inputValue, type) {
  var onError = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : defaultOnError;
  return coerceInputValueImpl(inputValue, type, onError);
}

function defaultOnError(path, invalidValue, error) {
  var errorPrefix = 'Invalid value ' + (0, _inspect.default)(invalidValue);

  if (path.length > 0) {
    errorPrefix += " at \"value".concat((0, _printPathArray.default)(path), "\": ");
  }

  error.message = errorPrefix + ': ' + error.message;
  throw error;
}

function coerceInputValueImpl(inputValue, type, onError, path) {
  if ((0, _definition.isNonNullType)(type)) {
    if (inputValue != null) {
      return coerceInputValueImpl(inputValue, type.ofType, onError, path);
    }

    onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Expected non-nullable type ".concat((0, _inspect.default)(type), " not to be null.")));
    return;
  }

  if (inputValue == null) {
    // Explicitly return the value null.
    return null;
  }

  if ((0, _definition.isListType)(type)) {
    var itemType = type.ofType;

    if ((0, _iterall.isCollection)(inputValue)) {
      var coercedValue = [];
      (0, _iterall.forEach)(inputValue, function (itemValue, index) {
        coercedValue.push(coerceInputValueImpl(itemValue, itemType, onError, (0, _Path.addPath)(path, index)));
      });
      return coercedValue;
    } // Lists accept a non-list value as a list of one.


    return [coerceInputValueImpl(inputValue, itemType, onError, path)];
  }

  if ((0, _definition.isInputObjectType)(type)) {
    if (!(0, _isObjectLike.default)(inputValue)) {
      onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Expected type ".concat(type.name, " to be an object.")));
      return;
    }

    var _coercedValue = {};
    var fieldDefs = type.getFields();

    for (var _i2 = 0, _objectValues2 = (0, _objectValues3.default)(fieldDefs); _i2 < _objectValues2.length; _i2++) {
      var field = _objectValues2[_i2];
      var fieldValue = inputValue[field.name];

      if (fieldValue === undefined) {
        if (field.defaultValue !== undefined) {
          _coercedValue[field.name] = field.defaultValue;
        } else if ((0, _definition.isNonNullType)(field.type)) {
          var typeStr = (0, _inspect.default)(field.type);
          onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Field ".concat(field.name, " of required type ").concat(typeStr, " was not provided.")));
        }

        continue;
      }

      _coercedValue[field.name] = coerceInputValueImpl(fieldValue, field.type, onError, (0, _Path.addPath)(path, field.name));
    } // Ensure every provided field is defined.


    for (var _i4 = 0, _Object$keys2 = Object.keys(inputValue); _i4 < _Object$keys2.length; _i4++) {
      var fieldName = _Object$keys2[_i4];

      if (!fieldDefs[fieldName]) {
        var suggestions = (0, _suggestionList.default)(fieldName, Object.keys(type.getFields()));
        onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Field \"".concat(fieldName, "\" is not defined by type ").concat(type.name, ".") + (0, _didYouMean.default)(suggestions)));
      }
    }

    return _coercedValue;
  }

  if ((0, _definition.isScalarType)(type)) {
    var parseResult; // Scalars determine if a input value is valid via parseValue(), which can
    // throw to indicate failure. If it throws, maintain a reference to
    // the original error.

    try {
      parseResult = type.parseValue(inputValue);
    } catch (error) {
      onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Expected type ".concat(type.name, ". ") + error.message, undefined, undefined, undefined, undefined, error));
      return;
    }

    if (parseResult === undefined) {
      onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Expected type ".concat(type.name, ".")));
    }

    return parseResult;
  }

  /* istanbul ignore else */
  if ((0, _definition.isEnumType)(type)) {
    if (typeof inputValue === 'string') {
      var enumValue = type.getValue(inputValue);

      if (enumValue) {
        return enumValue.value;
      }
    }

    var _suggestions = (0, _suggestionList.default)(String(inputValue), type.getValues().map(function (enumValue) {
      return enumValue.name;
    }));

    onError((0, _Path.pathToArray)(path), inputValue, new _GraphQLError.GraphQLError("Expected type ".concat(type.name, ".") + (0, _didYouMean.default)(_suggestions)));
    return;
  } // Not reachable. All possible input types have been considered.


  /* istanbul ignore next */
  (0, _invariant.default)(false, 'Unexpected input type: ' + (0, _inspect.default)(type));
}
