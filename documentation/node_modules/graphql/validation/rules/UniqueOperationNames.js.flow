// @flow strict

import { GraphQLError } from '../../error/GraphQLError';
import { type ASTVisitor } from '../../language/visitor';

import { type ASTValidationContext } from '../ValidationContext';

export function duplicateOperationNameMessage(operationName: string): string {
  return `There can be only one operation named "${operationName}".`;
}

/**
 * Unique operation names
 *
 * A GraphQL document is only valid if all defined operations have unique names.
 */
export function UniqueOperationNames(
  context: ASTValidationContext,
): ASTVisitor {
  const knownOperationNames = Object.create(null);
  return {
    OperationDefinition(node) {
      const operationName = node.name;
      if (operationName) {
        if (knownOperationNames[operationName.value]) {
          context.reportError(
            new GraphQLError(
              duplicateOperationNameMessage(operationName.value),
              [knownOperationNames[operationName.value], operationName],
            ),
          );
        } else {
          knownOperationNames[operationName.value] = operationName;
        }
      }
      return false;
    },
    FragmentDefinition: () => false,
  };
}
