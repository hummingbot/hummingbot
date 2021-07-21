// @flow strict

/* istanbul ignore file */
import { type GraphQLInputType } from '../type/definition';

import { coerceValue } from './coerceValue';

/**
 * Deprecated. Use coerceInputValue() directly for richer information.
 *
 * This function will be removed in v15
 */
export function isValidJSValue(
  value: mixed,
  type: GraphQLInputType,
): Array<string> {
  const errors = coerceValue(value, type).errors;
  return errors ? errors.map(error => error.message) : [];
}
