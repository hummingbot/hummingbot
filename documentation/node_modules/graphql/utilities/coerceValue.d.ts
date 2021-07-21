import { Path } from '../jsutils/Path';
import { GraphQLError } from '../error/GraphQLError';
import { ASTNode } from '../language/ast';
import { GraphQLInputType } from '../type/definition';

interface CoercedValue {
  readonly errors: ReadonlyArray<GraphQLError> | undefined;
  readonly value: any;
}

/**
 * Coerces a JavaScript value given a GraphQL Type.
 *
 * Returns either a value which is valid for the provided type or a list of
 * encountered coercion errors.
 *
 */
export function coerceValue(
  inputValue: any,
  type: GraphQLInputType,
  blameNode?: ASTNode,
  path?: Path,
): CoercedValue;
