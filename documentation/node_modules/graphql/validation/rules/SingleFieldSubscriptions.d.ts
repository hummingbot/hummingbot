import Maybe from '../../tsutils/Maybe';
import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function singleFieldOnlyMessage(name: Maybe<string>): string;

/**
 * Subscriptions must only include one field.
 *
 * A GraphQL subscription is valid only if it contains a single root field.
 */
export function SingleFieldSubscriptions(
  context: ASTValidationContext,
): ASTVisitor;
