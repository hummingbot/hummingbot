// @flow strict

import { GraphQLError } from '../../error/GraphQLError';

import { Kind } from '../../language/kinds';
import { type ASTVisitor } from '../../language/visitor';

import { type ASTValidationContext } from '../ValidationContext';

export function anonOperationNotAloneMessage(): string {
  return 'This anonymous operation must be the only defined operation.';
}

/**
 * Lone anonymous operation
 *
 * A GraphQL document is only valid if when it contains an anonymous operation
 * (the query short-hand) that it contains only that one operation definition.
 */
export function LoneAnonymousOperation(
  context: ASTValidationContext,
): ASTVisitor {
  let operationCount = 0;
  return {
    Document(node) {
      operationCount = node.definitions.filter(
        definition => definition.kind === Kind.OPERATION_DEFINITION,
      ).length;
    },
    OperationDefinition(node) {
      if (!node.name && operationCount > 1) {
        context.reportError(
          new GraphQLError(anonOperationNotAloneMessage(), node),
        );
      }
    },
  };
}
