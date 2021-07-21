import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function duplicateOperationNameMessage(operationName: string): string;

/**
 * Unique operation names
 *
 * A GraphQL document is only valid if all defined operations have unique names.
 */
export function UniqueOperationNames(context: ASTValidationContext): ASTVisitor;
