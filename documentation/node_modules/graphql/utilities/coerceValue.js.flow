// @flow strict

/* istanbul ignore file */
import inspect from '../jsutils/inspect';
import printPathArray from '../jsutils/printPathArray';
import { type Path, pathToArray } from '../jsutils/Path';

import { GraphQLError } from '../error/GraphQLError';
import { type ASTNode } from '../language/ast';
import { type GraphQLInputType } from '../type/definition';

import { coerceInputValue } from './coerceInputValue';

type CoercedValue = {|
  +errors: $ReadOnlyArray<GraphQLError> | void,
  +value: mixed,
|};

/**
 * Deprecated. Use coerceInputValue() directly for richer information.
 *
 * This function will be removed in v15
 */
export function coerceValue(
  inputValue: mixed,
  type: GraphQLInputType,
  blameNode?: ASTNode,
  path?: Path,
): CoercedValue {
  const errors = [];
  const value = coerceInputValue(
    inputValue,
    type,
    (errorPath, invalidValue, error) => {
      let errorPrefix = 'Invalid value ' + inspect(invalidValue);
      const pathArray = [...pathToArray(path), ...errorPath];
      if (pathArray.length > 0) {
        errorPrefix += ` at "value${printPathArray(pathArray)}"`;
      }
      errors.push(
        new GraphQLError(
          errorPrefix + ': ' + error.message,
          blameNode,
          undefined,
          undefined,
          undefined,
          error.originalError,
        ),
      );
    },
  );

  return errors.length > 0
    ? { errors, value: undefined }
    : { errors: undefined, value };
}
