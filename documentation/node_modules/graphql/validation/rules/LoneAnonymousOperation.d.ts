import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function anonOperationNotAloneMessage(): string;

/**
 * Lone anonymous operation
 *
 * A GraphQL document is only valid if when it contains an anonymous operation
 * (the query short-hand) that it contains only that one operation definition.
 */
export function LoneAnonymousOperation(
  context: ASTValidationContext,
): ASTVisitor;
