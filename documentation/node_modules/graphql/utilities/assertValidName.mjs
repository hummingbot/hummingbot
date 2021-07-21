import devAssert from '../jsutils/devAssert';
import { GraphQLError } from '../error/GraphQLError';
var NAME_RX = /^[_a-zA-Z][_a-zA-Z0-9]*$/;
/**
 * Upholds the spec rules about naming.
 */

export function assertValidName(name) {
  var error = isValidNameError(name);

  if (error) {
    throw error;
  }

  return name;
}
/**
 * Returns an Error if a name is invalid.
 */

export function isValidNameError(name, node) {
  typeof name === 'string' || devAssert(0, 'Expected string');

  if (name.length > 1 && name[0] === '_' && name[1] === '_') {
    return new GraphQLError("Name \"".concat(name, "\" must not begin with \"__\", which is reserved by GraphQL introspection."), node);
  }

  if (!NAME_RX.test(name)) {
    return new GraphQLError("Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/ but \"".concat(name, "\" does not."), node);
  }
}
