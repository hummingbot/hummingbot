/* istanbul ignore file */
import inspect from '../jsutils/inspect';
import printPathArray from '../jsutils/printPathArray';
import { pathToArray } from '../jsutils/Path';
import { GraphQLError } from '../error/GraphQLError';
import { coerceInputValue } from './coerceInputValue';

/**
 * Deprecated. Use coerceInputValue() directly for richer information.
 *
 * This function will be removed in v15
 */
export function coerceValue(inputValue, type, blameNode, path) {
  var errors = [];
  var value = coerceInputValue(inputValue, type, function (errorPath, invalidValue, error) {
    var errorPrefix = 'Invalid value ' + inspect(invalidValue);
    var pathArray = [].concat(pathToArray(path), errorPath);

    if (pathArray.length > 0) {
      errorPrefix += " at \"value".concat(printPathArray(pathArray), "\"");
    }

    errors.push(new GraphQLError(errorPrefix + ': ' + error.message, blameNode, undefined, undefined, undefined, error.originalError));
  });
  return errors.length > 0 ? {
    errors: errors,
    value: undefined
  } : {
    errors: undefined,
    value: value
  };
}
