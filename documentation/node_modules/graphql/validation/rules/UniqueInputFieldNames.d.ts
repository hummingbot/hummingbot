import { ASTVisitor } from '../../language/visitor';
import { ASTValidationContext } from '../ValidationContext';

export function duplicateInputFieldMessage(fieldName: string): string;

/**
 * Unique input field names
 *
 * A GraphQL input object value is only valid if all supplied fields are
 * uniquely named.
 */
export function UniqueInputFieldNames(
  context: ASTValidationContext,
): ASTVisitor;
